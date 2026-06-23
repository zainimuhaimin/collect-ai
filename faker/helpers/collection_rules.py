import random

def calculate_recovery_score(contract_no, df_payment, df_lkp):
    """Menghitung RECOVERY_SCORE berdasarkan Rule 1.1 - 1.4."""
    payments = df_payment[df_payment['CONTRACT_NO'] == contract_no]
    lkp_interactions = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]

    avg_delay_days = payments['DELAY_DAYS'].mean() if not payments.empty else 0
    avg_interaction_score = (
        lkp_interactions['INTERACTION_SCORE'].mean() if not lkp_interactions.empty else 0
    )

    if avg_delay_days <= 3:
        score = min(0.95 + random.uniform(-0.05, 0.05), 1.0)
    elif avg_delay_days <= 10:
        score = 0.85 + random.uniform(-0.05, 0.05)
    else:
        score = 0.70 + random.uniform(-0.10, 0.0)

    if avg_interaction_score == 0:
        pass
    elif avg_interaction_score >= 4.0:
        score = min(score + 0.10, 1.0)
    elif avg_interaction_score >= 3.0:
        pass
    elif avg_interaction_score >= 2.0:
        score = max(score - 0.15, 0.2)
    else:
        score = max(score - 0.30, 0.1)

    return score


def calculate_nba_recommendation(recovery_score, dpd_current, df_lkp, contract_no):
    """Menentukan NBA Recommendation berdasarkan recovery score dan historis interaksi."""
    lkp_interactions = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]

    if recovery_score > 0.80 and dpd_current < 15:
        return 'WA' if random.random() > 0.3 else 'SMS'

    if recovery_score >= 0.50:
        if not lkp_interactions.empty:
            call_results = lkp_interactions[lkp_interactions['TREATMENT_TYPE'].isin(['Deskcoll', 'Call'])]
            if not call_results.empty and (call_results['RESULT_CODE'] == 'PTP').any():
                return 'Deskcoll'
        return 'Call'

    if recovery_score >= 0.20:
        return 'Visit'

    return random.choice(['Somasi', 'Pickup'])


def calculate_priority_level(recovery_score, dpd_current, prnc_ots, nba_recommendation):
    """Menentukan priority level berdasarkan kombinasi faktor."""
    if prnc_ots > 15000000 and recovery_score >= 0.50 and nba_recommendation in ['Visit', 'Somasi']:
        return 'Critical'
    if (prnc_ots > 10000000 and recovery_score < 0.50) or (dpd_current > 60):
        return 'High'
    if (prnc_ots > 5000000 and recovery_score >= 0.50) or (dpd_current >= 30):
        return 'Medium'
    return 'Low'


def map_to_behavioral_grade(risk_segment):
    """Mapping Risk Segment ke Behavioral Grade."""
    mapping = {
        'Self-cure': 'A',
        'Can Pay': 'B',
        'Cannot Pay': 'C',
        "Won't Pay": 'D',
    }
    return mapping.get(risk_segment, 'C')


def calculate_recovery_effort_level(recovery_score, dpd_current, risk_segment):
    """Menentukan effort level yang diperlukan."""
    if risk_segment == 'Self-cure':
        return 'Low'
    if risk_segment == 'Can Pay':
        return 'High' if dpd_current > 30 else 'Mid'
    if risk_segment == 'Cannot Pay':
        return 'Mid'
    return 'High'


def calculate_ptp_reliability_index(contract_no, df_lkp):
    """Menghitung seberapa reliable nasabah dalam memenuhi janji bayar."""
    lkp_interactions = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]

    if lkp_interactions.empty:
        return 0.5

    ptp_count = len(lkp_interactions[lkp_interactions['RESULT_CODE'] == 'PTP'])
    if ptp_count == 0:
        return 0.7

    promise_fulfilled = len(
        lkp_interactions[lkp_interactions['RESULT_CODE'].isin(['Bayar', 'PTP'])]
    ) / 2

    reliability = (promise_fulfilled / ptp_count) * 0.8 + 0.2
    return min(reliability, 1.0)


def determine_collection_sensitivity(contract_no, df_lkp, recovery_score):
    """Menentukan metode collection yang paling efektif berdasarkan historis."""
    lkp_interactions = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]

    if lkp_interactions.empty:
        if recovery_score > 0.80:
            return 'WA'
        if recovery_score >= 0.50:
            return 'Call'
        return 'Visit'

    successful_wa = len(
        lkp_interactions[
            (lkp_interactions['TREATMENT_TYPE'] == 'WA')
            & (lkp_interactions['RESULT_CODE'].isin(['Bayar', 'PTP']))
        ]
    )
    successful_call = len(
        lkp_interactions[
            (lkp_interactions['TREATMENT_TYPE'].isin(['Deskcoll', 'Call']))
            & (lkp_interactions['RESULT_CODE'].isin(['Bayar', 'PTP']))
        ]
    )
    successful_visit = len(
        lkp_interactions[
            (lkp_interactions['TREATMENT_TYPE'] == 'Visit')
            & (lkp_interactions['RESULT_CODE'].isin(['Bayar', 'PTP']))
        ]
    )

    success_rates = {
        'WA': successful_wa,
        'Call': successful_call,
        'Visit': successful_visit,
    }
    best_method = max(success_rates, key=success_rates.get)
    return best_method if success_rates[best_method] > 0 else 'Call'


def determine_b_list_status(contract_no, df_lkp, recovery_score):
    """Menentukan apakah nasabah perlu masuk Problem Account List."""
    if recovery_score < 0.20:
        return True

    lkp_interactions = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]
    if lkp_interactions.empty:
        return False

    negative_results = len(
        lkp_interactions[lkp_interactions['RESULT_CODE'].isin(['Menolak', 'Rumah Kosong'])]
    )
    total_results = len(lkp_interactions)
    rejection_rate = negative_results / total_results if total_results > 5 else 0
    return rejection_rate > 0.5
