import { PDFLoader } from '@langchain/community/document_loaders/fs/pdf';
import { RecursiveCharacterTextSplitter } from '@langchain/textsplitters';
import { GoogleGenerativeAIEmbeddings } from '@langchain/google-genai';
import { Pinecone } from '@pinecone-database/pinecone';
import { PineconeStore } from '@langchain/pinecone';
import fs from 'fs';
import path from 'path';
import * as dotenv from 'dotenv';
dotenv.config();

async function main() {
  // Fix for Windows: decode URI and remove leading slash if present
  let __filename = new URL(import.meta.url).pathname;
  if (process.platform === 'win32' && __filename.startsWith('/')) {
    __filename = __filename.slice(1);
  }
  __filename = decodeURIComponent(__filename);
  const __dirname = path.dirname(__filename);
  const pdfDir = path.join(__dirname, 'PDFFiles');
  const files = fs.readdirSync(pdfDir);
  for (const file of files) {
    if (file.toLowerCase().endsWith('.pdf')) {
      const filePath = path.join(pdfDir, file);
      const loader = new PDFLoader(filePath);
      try {
        const docs = await loader.load();
        // Filter out empty docs
        const nonEmptyDocs = docs.filter(doc => doc.pageContent && doc.pageContent.trim().length > 0);
        if (nonEmptyDocs.length === 0) {
          console.warn(`No readable content in ${file}, skipping.`);
          continue;
        }
        const textSplitter = new RecursiveCharacterTextSplitter({
          chunkSize: 1000,
          chunkOverlap: 200,
        });
        const chunkedDocs = await textSplitter.splitDocuments(nonEmptyDocs);
        console.log(`File: ${file} | Original Docs: ${docs.length} | Non-empty Docs: ${nonEmptyDocs.length} | Chunked Docs: ${chunkedDocs.length}`);
        
        // Filter out empty chunks and add unique id to metadata
        const validChunks = chunkedDocs
          .filter(doc => doc.pageContent && doc.pageContent.trim().length > 0)
          .map((doc, idx) => {
            // Ensure metadata exists and has a unique id
            const meta = doc.metadata ? { ...doc.metadata } : {};
            meta.id = `${file}-${idx}`;
            return {
              ...doc,
              metadata: meta
            };
          });
        if (validChunks.length === 0) {
          console.warn(`No valid text chunks in ${file}, skipping.`);
          continue;
        }
        const embeddings = new GoogleGenerativeAIEmbeddings({
          apiKey: process.env.GEMINI_API_KEY,
          model: 'gemini-embedding-001',
        });

        let vectors = [];
        try {
          vectors = await embeddings.embedDocuments(validChunks.map(doc => doc.pageContent));
          // Log the raw vectors output for debugging
         
        } catch (embedErr) {
          console.error(`Embedding API error for ${file}:`, embedErr);
          continue;
        }

        // Filter out invalid vectors (should be arrays of numbers)
        const filtered = validChunks.map((doc, i) => ({
          doc,
          vector: vectors[i]
        })).filter(({ vector }) => Array.isArray(vector) && vector.length > 0 && vector.every(v => typeof v === 'number'));
        
        if (filtered.length === 0) {
          console.warn(`No valid embeddings for ${file}, skipping.`);
          continue;
        }
        const filteredChunks = filtered.map(f => f.doc);
        const filteredVectors = filtered.map(f => f.vector);
        console.log(`File: ${file} | filteredChunks: ${filteredChunks.length} | filteredVectors: ${filteredVectors.length}`);
        // Debug: log first vector and chunk
       
        const pinecone = new Pinecone();
        const pineconeIndex = (new Pinecone()).index(process.env.PINECONE_INDEX_NAME);
        // Final strict check before upsert
        if (filteredChunks.length > 0 && filteredVectors.length > 0 && filteredChunks.length === filteredVectors.length) {
          // Prepare records for Pinecone: each must have id, values, and metadata
          const pineconeRecords = filteredChunks.map((doc, i) => ({
            id: doc.metadata.id,
            values: filteredVectors[i],
            metadata: (() => {
              // Only allow string, number, boolean, or list of strings in metadata
              const meta = { ...doc.metadata };
              // Flatten 'loc' if present
              if (meta.loc && typeof meta.loc === 'object') {
                if (typeof meta.loc.pageNumber === 'number') {
                  meta.pageNumber = meta.loc.pageNumber;
                }
                // Remove or flatten other nested fields as needed
                delete meta.loc;
              }
              // Remove any other nested objects
              Object.keys(meta).forEach(key => {
                const v = meta[key];
                if (v && typeof v === 'object' && !Array.isArray(v)) {
                  delete meta[key];
                }
              });
              // Add the actual text content for retrieval
              meta.text = doc.pageContent;
              return meta;
            })()
          }));
          // Upsert directly using Pinecone client (bypassing fromDocuments if needed)
          if (pineconeRecords.length > 0) {
            // Log the first record and its vector dimension
            try {
              await pineconeIndex.upsert({ records: pineconeRecords });
              console.log(`Upserted ${pineconeRecords.length} records to Pinecone for ${file}`);
            } catch (upsertErr) {
              console.error('Pinecone upsert error details:', upsertErr);
            }
          } else {
            console.warn(`No valid records to upsert for ${file}.`);
          }
        } else {
          console.warn(`Upsert skipped for ${file}: No valid data to push to Pinecone.`);
        }

        console.log(`Successfully processed ${file}.`);
      } catch (err) {
        console.error(`Failed to load ${file}:`, err);
      }
    }
  }
}

main();