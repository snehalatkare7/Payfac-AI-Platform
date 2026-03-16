import { GoogleGenerativeAIEmbeddings } from '@langchain/google-genai';
import * as dotenv from 'dotenv';
dotenv.config();

async function testEmbedding() {
  const embeddings = new GoogleGenerativeAIEmbeddings({
    apiKey: process.env.GEMINI_API_KEY,
    model: 'gemini-embedding-001',
  });
  try {
    const result = await embeddings.embedDocuments(["hello world"]);
    console.log('Embedding result for "hello world":', result);
  } catch (err) {
    console.error('Embedding API error:', err);
  }
}

testEmbedding();
