from .retriever import retrieve_policies
from .compliance_utils import analyze_compliance
from sentence_transformers import SentenceTransformer

def compliance_agent(transaction):
    # Validate and insert policies from PDFs before compliance check
    brand = transaction["card_brand"]

    query_text = f"""
    Transaction review:

    amount: {transaction['amount']}
    merchant_mcc: {transaction['mcc']}
    merchant_country: {transaction['country']}
    chargeback_reason: {transaction.get('chargeback_reason','')}
    """

    # Generate embedding
    model = SentenceTransformer('all-MiniLM-L6-v2')

    query_embedding = model.encode(query_text).tolist()

    print("Generated query embedding for compliance agent.")

    # Retrieve policies
    policies = retrieve_policies(query_embedding, brand)

    policy_context = "\n".join(
        [p["rule_text"] for p in policies]
    )

    print(f"Retrieved {len(policies)} relevant policies for brand {brand}.")

    prompt = f"""
Transaction:
{transaction}

Relevant {brand} policies:
{policy_context}

Determine compliance risk.

Return JSON:

{{
 "policy_violation": true/false,
 "applicable_rule": "",
 "risk_score": 0-100,
 "recommendation": "",
 "explanation": ""
}}
"""

    result = analyze_compliance(prompt)

    print("Compliance agent result:", result)

    return result

if __name__ == "__main__":
    # Example transaction for testing
    transaction = {
        "card_brand": "visa",
        "amount": 100.0,
        "mcc": "5411",
        "country": "US",
        "chargeback_reason": "fraudulent transaction"
    }
    result = compliance_agent(transaction)
    print("Compliance Agent Output:", result)

