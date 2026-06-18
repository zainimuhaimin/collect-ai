import pandas as pd
import numpy as np
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker('id_ID')

# Setup Parameter Jumlah Data
NUM_CUSTOMERS = 1000

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
        num_contracts = random.choices([1, 2], weights=[0.8, 0.2])[0] 
        for j in range(num_contracts):
            contract_no = f"CTR-{row['CUST_ID'].split('-')[1]}-{j+1}"
            dpd = random.choices([0, 15, 45, 75, 120], weights=[0.4, 0.3, 0.15, 0.1, 0.05])[0] + random.randint(0, 10)
            
            if dpd == 0: cycle = 'C0'
            elif dpd <= 30: cycle = 'C1'
            elif dpd <= 60: cycle = 'C2'
            else: cycle = 'C3+'
            
            data.append({
                'CONTRACT_NO': contract_no,
                'CUST_ID': row['CUST_ID'],
                'DPD_CURRENT': dpd,
                'PRNC_OTS': round(random.uniform(1000000, 20000000), 2),
                'INTR_OTS': round(random.uniform(100000, 2000000), 2),
                'CYCLE_AKHIR': cycle,
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
        num_payments = random.randint(3, 4) 
        base_due_date = datetime.now() - timedelta(days=30 * num_payments)
        
        behavior_type = random.choice(['ON_TIME', 'LATE_FEW_DAYS', 'LATE_WEEKS'])
        
        for i in range(num_payments):
            due_date = base_due_date + timedelta(days=30 * i)
            
            if behavior_type == 'ON_TIME':
                delay = random.randint(-5, 0)
            elif behavior_type == 'LATE_FEW_DAYS':
                delay = random.randint(1, 10)
            else:
                delay = random.randint(11, 45)
                
            actual_pay_date = due_date + timedelta(days=delay)
            pay_amount = round(random.uniform(500000, 1500000), 2)
            
            data.append({
                'PAYMENT_ID': f"PAY-{pay_id_counter:07d}",
                'CONTRACT_NO': row['CONTRACT_NO'],
                'DUE_DATE': due_date.strftime('%Y-%m-%d'),
                'ACTUAL_PAY_DATE': actual_pay_date.strftime('%Y-%m-%d'),
                'PAYMENT_AMOUNT': pay_amount,
                'PAY_STATUS': random.choice(['Full', 'Partial', 'Overpaid']),
                'PAY_METHOD': random.choice(['Autodebet', 'VA', 'Kasir', 'Transfer Bank']),
                'DELAY_DAYS': delay if delay > 0 else 0
            })
            pay_id_counter += 1
    return pd.DataFrame(data)

df_payment = generate_payment_history(df_contract)

# ==========================================
# 4. LKP & INTERACTION HISTORY (UPDATED LOGIC)
# ==========================================
def generate_lkp_history(df_contr):
    data = []
    lkp_id_counter = 1
    for index, row in df_contr.iterrows():
        if row['DPD_CURRENT'] > 0:
            num_interactions = random.randint(1, 5)
            for i in range(num_interactions):
                action_date = datetime.now() - timedelta(days=random.randint(1, row['DPD_CURRENT']))
                treatment = random.choice(['WA', 'SMS', 'Deskcoll', 'Visit', 'Somasi'])
                result = random.choice(['Bayar', 'PTP', 'Rumah Kosong', 'Menolak'])
                
                promise_date = action_date + timedelta(days=random.randint(1, 7)) if result == 'PTP' else None
                
                # --- LOGIKA INTERACTION SCORE BARU ---
                if result == 'Bayar':
                    # Kalau bayar, nasabah sangat kooperatif
                    int_score = random.choice([4, 5])
                elif result == 'PTP':
                    # Kalau janji bayar, nasabah cukup kooperatif
                    int_score = random.choice([3, 4])
                elif result == 'Rumah Kosong':
                    # Kalau kosong, interaksi tidak ada atau minim
                    int_score = random.choice([2, 3])
                else: # Menolak
                    # Kalau menolak, nasabah tidak kooperatif / kasar
                    int_score = random.choice([1, 2])
                
                data.append({
                    'LKP_ID': f"LKP-{lkp_id_counter:06d}",
                    'CONTRACT_NO': row['CONTRACT_NO'],
                    'ACTION_DATE': action_date.strftime('%Y-%m-%d'),
                    'TREATMENT_TYPE': treatment,
                    'RESULT_CODE': result,
                    'PROMISE_DATE': promise_date.strftime('%Y-%m-%d') if promise_date else '',
                    'COLLECTOR_ID': f"COLL-{random.randint(1, 50):03d}",
                    'INTERACTION_SCORE': int_score
                })
                lkp_id_counter += 1
    return pd.DataFrame(data)

df_lkp = generate_lkp_history(df_contract)

# ==========================================
# 5. AI INTELLIGENCE OUTPUT
# ==========================================
def generate_ai_output(df_contr):
    data = []
    for index, row in df_contr.iterrows():
        score = random.uniform(0.1, 0.9) if row['DPD_CURRENT'] > 30 else random.uniform(0.6, 0.99)
        
        if score > 0.8: segment = 'Self-cure'
        elif score > 0.5: segment = 'Can Pay'
        elif score > 0.2: segment = 'Cannot Pay'
        else: segment = "Won't Pay"
        
        data.append({
            'CONTRACT_NO': row['CONTRACT_NO'],
            'RECOVERY_SCORE': round(score, 4),
            'RISK_SEGMENT': segment,
            'NBA_RECOMMENDATION': random.choice(['WA', 'Visit', 'Somasi', 'Pickup']),
            'PRIORITY_LEVEL': random.choice(['Low', 'Medium', 'High', 'Critical']),
            'CONFIDENCE_LEVEL': round(random.uniform(0.7, 0.99), 4)
        })
    return pd.DataFrame(data)

df_ai_output = generate_ai_output(df_contract)

# ==========================================
# 6. CUSTOMER BEHAVIORAL STANDING
# ==========================================
def generate_behavioral_standing(df_cust, df_contr):
    data = []
    for index, row in df_cust.iterrows():
        cust_contracts = df_contr[df_contr['CUST_ID'] == row['CUST_ID']]
        if not cust_contracts.empty:
            last_contract = cust_contracts.iloc[-1]['CONTRACT_NO']
            data.append({
                'CUST_ID': row['CUST_ID'],
                'LAST_CONTRACT_NO': last_contract,
                'BEHAVIORAL_GRADE': random.choice(['A', 'B', 'C', 'D']),
                'RECOVERY_EFFORT_LEVEL': random.choice(['Low', 'Mid', 'High']),
                'PTP_RELIABILITY_INDEX': round(random.uniform(0.0, 1.0), 2),
                'COLLECTION_SENSITIVITY': random.choice(['WA', 'Call', 'Visit']),
                'B_LIST_STATUS': random.choice([True, False]),
                'UPDATE_TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    return pd.DataFrame(data)

df_behavioral = generate_behavioral_standing(df_customer, df_contract)

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
    df_ai_output.to_excel(writer, sheet_name='5_AI_Intelligence', index=False)
    df_behavioral.to_excel(writer, sheet_name='6_Customer_Behavioral', index=False)

print(f"Berhasil! Data telah disimpan di {excel_filename} dengan 6 sheet berbeda.")