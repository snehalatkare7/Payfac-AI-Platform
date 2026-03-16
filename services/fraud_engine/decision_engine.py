def decide(risk_score):

    if risk_score > 700:
        return "DECLINE"

    if risk_score > 300:
        return "STEP_UP_AUTH"

    return "APPROVE"