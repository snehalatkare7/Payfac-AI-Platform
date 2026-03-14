def risk_score(txn):

    score = 0

    if txn["amount"] > 500:
        score += 200

    if txn["geo_location"] not in ["home_country"]:
        score += 300

    if txn["mcc"] in ["7995", "4829"]:
        score += 200

    return score