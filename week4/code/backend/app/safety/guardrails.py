def guard_action(action: dict) -> dict:
    content = action.get('content', '')
    high_risk_keywords = ['静推', '剂量', '立即用药', '处方']
    if any(keyword in content for keyword in high_risk_keywords):
        return {'allowed': False, 'reason': 'clinical_high_risk'}
    return {'allowed': True, 'reason': 'ok'}
