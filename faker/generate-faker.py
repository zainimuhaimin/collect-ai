import random
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

# from helpers.collection_rules import (
#     calculate_nba_recommendation,
#     calculate_priority_level,
#     calculate_ptp_reliability_index,
#     calculate_recovery_effort_level,
#     calculate_recovery_score,
#     determine_b_list_status,
#     determine_collection_sensitivity,
#     map_to_behavioral_grade,
# )
from helpers.database import append_dataframes_to_postgres

fake = Faker('id_ID')

# Setup Parameter Jumlah Data
NUM_CUSTOMERS = 100

print("Mulai menghasilkan data dummy...")

# ==========================================
# 1. CUSTOMER MASTER
# ==========================================
def generate_customer_master(n):
    data = []
    for i in range(1, n + 1):
        data.append({
            'CUST_ID': f'CUST-{i:05d}',
            'CUST_AGE': random.randint(18, 80),
            'CUST_OCCUPATION': random.choice(['Karyawan Swasta', 'PNS/TNI/Polri', 'Wiraswasta', 'Buruh', 'Profesional', 'Lainnya']),
            'CUST_INCOME_LEVEL': random.choice(['< 3 Juta', '3-5 Juta', '5-10 Juta', '10-20 Juta', '> 20 Juta']),
            'CUST_REGION': fake.city_name(),
            'CUST_PHONE': fake.phone_number(),
            'CUST_SEGMENT': random.choice(['Low Risk', 'Medium Risk', 'High Risk'])
        })
    return pd.DataFrame(data)

df_customer = generate_customer_master(NUM_CUSTOMERS)

# ==========================================
# 2. CONTRACT SNAPSHOT
# ==========================================
def generate_contract_snapshot(df_cust):
    data = []
    for index, row in df_cust.iterrows():
        # jumlah kontrak per customer
        num_contracts = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.1])[0]
        for j in range(num_contracts):
            contract_no = f"CTR-{row['CUST_ID'].split('-')[1]}-{j+1}"

            # Tentukan PRNC_OTS berdasarkan level income nasabah agar konsisten
            income = row['CUST_INCOME_LEVEL']
            if income == '< 3 Juta':
                prnc = round(random.uniform(1000000, 3000000), 2)
            elif income == '3-5 Juta':
                prnc = round(random.uniform(2000000, 6000000), 2)
            elif income == '5-10 Juta':
                prnc = round(random.uniform(5000000, 10000000), 2)
            elif income == '10-20 Juta':
                prnc = round(random.uniform(8000000, 15000000), 2)
            else:  # > 20 Juta
                prnc = round(random.uniform(10000000, 20000000), 2)

            # Modulate DPD probabilities by income (lower income => slightly higher chance of DPD)
            base_choices = [0, 15, 45, 75, 120]
            base_weights = [0.45, 0.30, 0.15, 0.07, 0.03]
            if income in ['< 3 Juta', '3-5 Juta']:
                # increase chance for higher DPD
                base_weights = [0.35, 0.30, 0.20, 0.10, 0.05]

            dpd = random.choices(base_choices, weights=base_weights)[0] + random.randint(0, 10)
            if dpd <= 0:
                cycle = 'C0'
            elif dpd <= 30:
                cycle = 'C1'
            elif dpd <= 60:
                cycle = 'C2'
            else:
                cycle = 'C3+'

            data.append({
                'CONTRACT_NO': contract_no,
                'CUST_ID': row['CUST_ID'],
                'DPD_CURRENT': dpd,
                'PRNC_OTS': prnc,
                'INTR_OTS': round(prnc * 0.1, 2),
                'CYCLE': cycle,
                'PRODUCT_TYPE': random.choice(['Motor', 'Elektronik & Furnitur', 'Haji & Umrah', 'Dana Tunai', 'Modal Usaha'])
            })
    return pd.DataFrame(data)

df_contract = generate_contract_snapshot(df_customer)

# ==========================================
# 3. PAYMENT HISTORY
# ==========================================
def generate_payment_history(df_contr):
    data = []
    pay_id_counter = 1
    for index, row in df_contr.iterrows():
        # Tentukan tenor/history length berdasarkan product type & principal
        num_payments = random.randint(1, 12)
        base_due_date = datetime.now() - timedelta(days=30 * num_payments)

        # behavior influenced by DPD_CURRENT: higher DPD -> more late behavior
        if row['DPD_CURRENT'] == 0:
            behavior_probs = [0.7, 0.2, 0.1]
        elif row['DPD_CURRENT'] <= 30:
            behavior_probs = [0.4, 0.4, 0.2]
        elif row['DPD_CURRENT'] <= 60:
            behavior_probs = [0.2, 0.4, 0.4]
        else:
            behavior_probs = [0.1, 0.3, 0.6]

        behavior_type = random.choices(['ON_TIME', 'LATE_FEW_DAYS', 'LATE_WEEKS'], weights=behavior_probs)[0]

        # Estimate a base installment amount from principal
        est_installment = max(500000, round(row['PRNC_OTS'] / max(1, num_payments)))

        for i in range(num_payments):
            due_date = base_due_date + timedelta(days=30 * i)

            # make last payment reflect current DPD
            if i == num_payments - 1 and row['DPD_CURRENT'] > 0:
                delay = row['DPD_CURRENT'] + random.randint(0, 5)
            else:
                if behavior_type == 'ON_TIME':
                    delay = random.randint(-5, 3)
                elif behavior_type == 'LATE_FEW_DAYS':
                    delay = random.randint(1, 12)
                else:
                    delay = random.randint(11, 60)

            actual_pay_date = due_date + timedelta(days=delay)

            # Payment amount tends to be around installment, but partial/overpay possible
            if delay <= 3:
                pay_status = random.choices(['Full', 'Overpaid'], weights=[0.85, 0.15])[0]
                pay_amount = round(est_installment * random.uniform(0.95, 1.2), 2)
            elif delay <= 15:
                pay_status = random.choices(['Partial', 'Full'], weights=[0.6, 0.4])[0]
                pay_amount = round(est_installment * random.uniform(0.5, 1.0), 2)
            else:
                pay_status = random.choices(['Partial', 'Full', 'Overpaid'], weights=[0.7, 0.25, 0.05])[0]
                pay_amount = round(est_installment * random.uniform(0.2, 0.9), 2)

            data.append({
                'PAYMENT_ID': f"PAY-{pay_id_counter:07d}",
                'CONTRACT_NO': row['CONTRACT_NO'],
                'DUE_DATE': due_date.strftime('%Y-%m-%d'),
                'ACTUAL_PAY_DATE': actual_pay_date.strftime('%Y-%m-%d'),
                'PAYMENT_AMOUNT': pay_amount,
                'PAY_STATUS': pay_status,
                'PAY_METHOD': random.choice(['Autodebet', 'VA', 'Kasir', 'Transfer Bank']),
                'DELAY_DAYS': delay if delay > 0 else 0
            })
            pay_id_counter += 1
    return pd.DataFrame(data)

df_payment = generate_payment_history(df_contract)

# ==========================================
# 4. LKP & INTERACTION HISTORY
# ==========================================
def generate_lkp_history(df_contr):
    data = []
    lkp_id_counter = 1
    for index, row in df_contr.iterrows():
        if row['DPD_CURRENT'] > 0:
            # lebih besar DPD => lebih banyak interaksi
            max_interactions = min(25, 1 + int(row['DPD_CURRENT'] / 5))
            num_interactions = random.randint(1, max_interactions)
            for i in range(num_interactions):
                # action date biased towards recent days when DPD is high
                lookback = max(1, row['DPD_CURRENT'])
                action_date = datetime.now() - timedelta(days=random.randint(1, lookback))

                # Treatment selection biased by DPD
                if row['DPD_CURRENT'] <= 15:
                    treatment = random.choices(['WA', 'SMS', 'Deskcoll'], weights=[0.5, 0.3, 0.2])[0]
                elif row['DPD_CURRENT'] <= 60:
                    treatment = random.choices(['Deskcoll', 'WA', 'Visit'], weights=[0.4, 0.3, 0.3])[0]
                else:
                    treatment = random.choices(['Visit', 'Somasi', 'Pickup'], weights=[0.4, 0.3, 0.3])[0]

                # Result probability depends on DPD
                if row['DPD_CURRENT'] <= 15:
                    result = random.choices(['Bayar', 'PTP', 'Menolak', 'Rumah Kosong'], weights=[0.4, 0.35, 0.15, 0.1])[0]
                elif row['DPD_CURRENT'] <= 60:
                    result = random.choices(['PTP', 'Bayar', 'Menolak', 'Rumah Kosong'], weights=[0.35, 0.25, 0.25, 0.15])[0]
                else:
                    result = random.choices(['Menolak', 'Rumah Kosong', 'PTP', 'Bayar'], weights=[0.45, 0.25, 0.2, 0.1])[0]

                promise_date = action_date + timedelta(days=random.randint(1, 14)) if result == 'PTP' else None

                # Interaction score mapping
                if result == 'Bayar':
                    int_score = random.choice([4, 5])
                elif result == 'PTP':
                    int_score = random.choice([3, 4])
                elif result == 'Rumah Kosong':
                    int_score = random.choice([1, 2])
                else:  # Menolak
                    int_score = random.choice([1, 2])

                data.append({
                    'LKP_ID': f"LKP-{lkp_id_counter:06d}",
                    'CONTRACT_NO': row['CONTRACT_NO'],
                    'ACTION_DATE': action_date.strftime('%Y-%m-%d'),
                    'TREATMENT_TYPE': treatment,
                    'RESULT_CODE': result,
                    'PROMISE_DATE': promise_date.strftime('%Y-%m-%d') if promise_date else '',
                    'COLLECTOR_ID': f"COLL-{random.randint(1, 30):03d}",
                    'INTERACTION_SCORE': int_score
                })
                lkp_id_counter += 1
    return pd.DataFrame(data)

df_lkp = generate_lkp_history(df_contract)

# def generate_collection_analysis(df_contr, df_payment, df_lkp):
#     data = []
#     for _, row in df_contr.iterrows():
#         contract_no = row['CONTRACT_NO']
#         cust_id = row['CUST_ID']
#         dpd_current = row['DPD_CURRENT']
#         prnc_ots = row['PRNC_OTS']

#         recovery_score = calculate_recovery_score(contract_no, df_payment, df_lkp)

#         if dpd_current > 60:
#             recovery_score = max(recovery_score * 0.6, 0.15)
#         elif dpd_current > 30:
#             recovery_score = max(recovery_score * 0.8, 0.25)

#         if prnc_ots > 15000000 and dpd_current > 30:
#             recovery_score = max(recovery_score - 0.15, 0.1)

#         recovery_score = max(min(recovery_score, 1.0), 0.0)

#         if recovery_score > 0.80 and dpd_current < 15:
#             segment = 'Self-cure'
#         elif recovery_score >= 0.50:
#             segment = 'Can Pay'
#         elif recovery_score >= 0.20:
#             segment = 'Cannot Pay'
#         else:
#             segment = "Won't Pay"

#         nba_rec = calculate_nba_recommendation(recovery_score, dpd_current, df_lkp, contract_no)
#         priority = calculate_priority_level(recovery_score, dpd_current, prnc_ots, nba_rec)

#         lkp_count = len(df_lkp[df_lkp['CONTRACT_NO'] == contract_no])
#         payment_count = len(df_payment[df_payment['CONTRACT_NO'] == contract_no])
#         base_confidence = 0.70 + (min(lkp_count, 5) * 0.05) + (min(payment_count, 4) * 0.02)
#         confidence_level = min(base_confidence, 0.99)

#         data.append({
#             'contract_no': contract_no,
#             'cust_id': cust_id,
#             'recovery_score': round(recovery_score, 4),
#             'risk_segment': segment,
#             'nba_recommendation': nba_rec,
#             'priority_level': priority,
#             'confidence_level': round(confidence_level, 4),
#             'scoring_date': datetime.now().date(),
#         })
#     return pd.DataFrame(data)


# def generate_customer_analysis(df_cust, df_contr, df_lkp, df_ai_output):
#     data = []
#     for _, row in df_cust.iterrows():
#         cust_id = row['CUST_ID']
#         cust_contracts = df_contr[df_contr['CUST_ID'] == cust_id]

#         if cust_contracts.empty:
#             continue

#         last_contract = cust_contracts.iloc[-1]
#         last_contract_no = last_contract['CONTRACT_NO']

#         ai_output = df_ai_output[df_ai_output['contract_no'] == last_contract_no]
#         if not ai_output.empty:
#             recovery_score = ai_output.iloc[0]['recovery_score']
#             risk_segment = ai_output.iloc[0]['risk_segment']
#         else:
#             recovery_score = 0.5
#             risk_segment = 'Can Pay'

#         behavioral_grade = map_to_behavioral_grade(risk_segment)
#         recovery_effort = calculate_recovery_effort_level(
#             recovery_score,
#             last_contract['DPD_CURRENT'],
#             risk_segment,
#         )
#         ptp_reliability = calculate_ptp_reliability_index(last_contract_no, df_lkp)
#         collection_sensitivity = determine_collection_sensitivity(last_contract_no, df_lkp, recovery_score)
#         b_list_status = determine_b_list_status(last_contract_no, df_lkp, recovery_score)

#         data.append({
#             'cust_id': cust_id,
#             'active_contract_count': int(len(cust_contracts)),
#             'total_active_ots': round(float(cust_contracts['PRNC_OTS'].sum()), 2),
#             'behavioral_grade': behavioral_grade,
#             'recovery_effort_level': recovery_effort,
#             'ptp_reliability_index': round(ptp_reliability, 2),
#             'collection_sensitivity': collection_sensitivity,
#             'b_list_status': b_list_status,
#             'update_timestamp': datetime.now(),
#         })

#     return pd.DataFrame(data)


df_customer = generate_customer_master(NUM_CUSTOMERS)
df_contract = generate_contract_snapshot(df_customer)
df_payment = generate_payment_history(df_contract)
df_lkp = generate_lkp_history(df_contract)
# df_ai_output = generate_collection_analysis(df_contract, df_payment, df_lkp)
# df_behavioral = generate_customer_analysis(df_customer, df_contract, df_lkp, df_ai_output)


# ==========================================
# EXPORT KE 1 FILE EXCEL (MULTI-SHEET)
# ==========================================
print("Menyimpan ke dalam file Excel...")

excel_filename = "Dataset_CollectAI_Dummy.xlsx"

with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
    df_customer.to_excel(writer, sheet_name='1_Customer_Master', index=False)
    df_contract.to_excel(writer, sheet_name='2_Contract_Snapshot', index=False)
    df_payment.to_excel(writer, sheet_name='3_Payment_History', index=False)
    df_lkp.to_excel(writer, sheet_name='4_LKP_Interaction', index=False)
    # df_ai_output.to_excel(writer, sheet_name='5_Collection_Analysis', index=False)
    # df_behavioral.to_excel(writer, sheet_name='6_Customer_Analysis', index=False)

print(f"Berhasil! Data telah disimpan di {excel_filename} dengan sheet berbeda.")


# ==========================================
# EXPORT KE POSTGRESQL
# ==========================================
db_tables = {
    'customer_master': df_customer,
    'contract_snapshot': df_contract,
    'payment_history': df_payment,
    'lkp_interaction': df_lkp,
    # 'collection_analysis': df_ai_output,
    # 'customer_analysis': df_behavioral,
}

append_dataframes_to_postgres(db_tables, if_exists='append')