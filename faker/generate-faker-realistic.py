"""
Generate realistic synthetic data for CollectAI with strong predictive signals.
Key principle: Features should ACTUALLY predict payment behavior.
"""
import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from faker import Faker

from helpers.database import append_dataframes_to_postgres

fake = Faker('id_ID')

# Setup Parameters
NUM_CUSTOMERS = 500  # Increased for better model training
PAYMENT_HISTORY_MONTHS = 12

print("=" * 60)
print("Generating REALISTIC data for CollectAI...")
print("=" * 60)


def assign_default_probability(income_level, age, occupation):
    """
    Assign hidden default probability based on socioeconomic factors.
    Higher income + stable job = lower default probability.
    """
    # Base probability from income
    income_probs = {
        '< 3 Juta': 0.45,
        '3-5 Juta': 0.35,
        '5-10 Juta': 0.25,
        '10-20 Juta': 0.15,
        '> 20 Juta': 0.08,
    }
    base_prob = income_probs.get(income_level, 0.30)

    # Age adjustment (very young or very old = higher risk)
    if age < 25 or age > 65:
        base_prob += 0.10
    elif age > 55:
        base_prob += 0.05

    # Occupation adjustment (stability factor)
    occupation_adjustments = {
        'PNS/TNI/Polri': -0.12,  # Very stable
        'Profesional': -0.08,
        'Karyawan Swasta': -0.02,
        'Wiraswasta': 0.08,
        'Buruh': 0.15,
        'Lainnya': 0.05,
    }
    base_prob += occupation_adjustments.get(occupation, 0)

    # Clamp between 0.05 and 0.85
    return max(0.05, min(0.85, base_prob))


# ==========================================
# 1. CUSTOMER MASTER
# ==========================================
def generate_customer_master(n):
    data = []
    customer_true_defaults = {}

    for i in range(1, n + 1):
        cust_id = f'CUST-{i:05d}'
        age = random.randint(22, 70)
        income_level = random.choice(
            ['< 3 Juta', '3-5 Juta', '5-10 Juta', '10-20 Juta', '> 20 Juta']
        )
        occupation = random.choice(
            ['Karyawan Swasta', 'PNS/TNI/Polri', 'Wiraswasta', 'Buruh', 'Profesional', 'Lainnya']
        )

        # Assign hidden default probability
        default_prob = assign_default_probability(income_level, age, occupation)
        customer_true_defaults[cust_id] = default_prob

        data.append({
            'CUST_ID': cust_id,
            'CUST_AGE': age,
            'CUST_OCCUPATION': occupation,
            'CUST_INCOME_LEVEL': income_level,
            'CUST_REGION': fake.city_name(),
            'CUST_PHONE': fake.phone_number(),
            'CUST_SEGMENT': 'High Risk' if default_prob > 0.50 else
                           'Medium Risk' if default_prob > 0.25 else
                           'Low Risk',
        })

    return pd.DataFrame(data), customer_true_defaults


# ==========================================
# 2. CONTRACT SNAPSHOT
# ==========================================
def generate_contract_snapshot(df_cust, customer_true_defaults):
    data = []
    contract_default_probs = {}

    for index, row in df_cust.iterrows():
        cust_id = row['CUST_ID']
        num_contracts = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.1])[0]

        for j in range(num_contracts):
            contract_no = f"CTR-{row['CUST_ID'].split('-')[1]}-{j+1}"

            # Principal based on income (realistic constraint)
            income = row['CUST_INCOME_LEVEL']
            if income == '< 3 Juta':
                prnc = round(random.uniform(1000000, 3000000), 2)
            elif income == '3-5 Juta':
                prnc = round(random.uniform(2000000, 6000000), 2)
            elif income == '5-10 Juta':
                prnc = round(random.uniform(5000000, 12000000), 2)
            elif income == '10-20 Juta':
                prnc = round(random.uniform(8000000, 20000000), 2)
            else:  # > 20 Juta
                prnc = round(random.uniform(12000000, 30000000), 2)

            # DPD is CONSEQUENCE of default probability + payment history
            # High default probability -> higher chance of DPD
            cust_default_prob = customer_true_defaults[cust_id]
            dpd_choices = [0, 15, 45, 90, 150]
            dpd_weights = [
                1.0 - cust_default_prob,           # Current
                cust_default_prob * 0.25,          # 15 DPD
                cust_default_prob * 0.30,          # 45 DPD
                cust_default_prob * 0.25,          # 90 DPD
                cust_default_prob * 0.20,          # 150 DPD
            ]
            dpd_weights = np.array(dpd_weights)
            dpd_weights /= dpd_weights.sum()  # Normalize
            dpd = int(np.random.choice(dpd_choices, p=dpd_weights)) + random.randint(-3, 3)
            dpd = max(0, dpd)

            if dpd <= 0:
                cycle = 'C0'
            elif dpd <= 30:
                cycle = 'C1'
            elif dpd <= 60:
                cycle = 'C2'
            else:
                cycle = 'C3+'

            # Contract-level default probability influenced by DPD
            contract_default_prob = cust_default_prob + (dpd / 150) * 0.15
            contract_default_prob = min(0.95, contract_default_prob)
            contract_default_probs[contract_no] = contract_default_prob

            data.append({
                'CONTRACT_NO': contract_no,
                'CUST_ID': cust_id,
                'DPD_CURRENT': dpd,
                'PRNC_OTS': prnc,
                'INTR_OTS': round(prnc * 0.10, 2),
                'CYCLE': cycle,
                'PRODUCT_TYPE': random.choice(['Motor', 'Elektronik & Furnitur', 'Haji & Umrah', 'Dana Tunai', 'Modal Usaha'])
            })

    return pd.DataFrame(data), contract_default_probs


# ==========================================
# 3. PAYMENT HISTORY (KEY: Sticky Behavior)
# ==========================================
def generate_payment_history(df_contr, contract_default_probs):
    """
    Payment history follows customer's default probability with STICKY BEHAVIOR.
    Once a customer establishes pattern (payer/defaulter), they mostly maintain it.
    """
    data = []
    pay_id_counter = 1
    contract_behaviors = {}  # Track established behavior for each contract

    for index, row in df_contr.iterrows():
        contract_no = row['CONTRACT_NO']
        dpd_current = row['DPD_CURRENT']
        prnc_ots = row['PRNC_OTS']
        default_prob = contract_default_probs[contract_no]

        num_payments = random.randint(6, 18)
        base_due_date = datetime.now() - timedelta(days=30 * num_payments)

        # Assign behavior pattern for this contract at inception
        will_eventually_default = random.random() < default_prob
        contract_behaviors[contract_no] = will_eventually_default

        # Behavior consistency: once established, 85% stick with it
        behavior_consistency = 0.85
        est_installment = max(500000, round(prnc_ots / max(1, num_payments)))

        for i in range(num_payments):
            due_date = base_due_date + timedelta(days=30 * i)

            # Determine if payment for THIS month
            if i < num_payments - 1:
                # Historic payments: high consistency
                should_pay = random.random() < (1.0 - default_prob + behavior_consistency)
            else:
                # Last payment: reflects current DPD
                should_pay = dpd_current <= 30

            if should_pay:
                # Good payer: pay on-time or few days late
                delay = random.choices(
                    [-5, -2, 0, 3, 7],
                    weights=[0.05, 0.10, 0.60, 0.20, 0.05]
                )[0]
                pay_status = random.choices(['Full', 'Overpaid'], weights=[0.90, 0.10])[0]
                pay_amount = round(est_installment * random.uniform(0.98, 1.15), 2)
            else:
                # Problem payer: late, partial, or skip
                if random.random() < 0.40:
                    # Skip month (will appear as missed)
                    continue
                else:
                    delay = random.choices(
                        [15, 30, 45, 60, 90],
                        weights=[0.30, 0.25, 0.20, 0.15, 0.10]
                    )[0] + random.randint(0, 10)
                    pay_status = random.choices(['Partial', 'Full'], weights=[0.70, 0.30])[0]
                    pay_amount = round(est_installment * random.uniform(0.20, 0.80), 2)

            actual_pay_date = due_date + timedelta(days=delay)

            data.append({
                'PAYMENT_ID': f"PAY-{pay_id_counter:07d}",
                'CONTRACT_NO': contract_no,
                'DUE_DATE': due_date.strftime('%Y-%m-%d'),
                'ACTUAL_PAY_DATE': actual_pay_date.strftime('%Y-%m-%d'),
                'PAYMENT_AMOUNT': pay_amount,
                'PAY_STATUS': pay_status,
                'PAY_METHOD': random.choice(['Autodebet', 'VA', 'Kasir', 'Transfer Bank', 'COD']),
                'DELAY_DAYS': max(0, delay),
            })
            pay_id_counter += 1

    return pd.DataFrame(data), contract_behaviors


# ==========================================
# 4. LKP INTERACTION HISTORY
# ==========================================
def generate_lkp_history(df_contr, contract_default_probs, contract_behaviors):
    """
    Interactions should show realistic collection outcomes.
    High default probability = more interactions, worse results.
    """
    data = []
    lkp_id_counter = 1

    for index, row in df_contr.iterrows():
        contract_no = row['CONTRACT_NO']
        dpd_current = row['DPD_CURRENT']
        default_prob = contract_default_probs[contract_no]
        will_default = contract_behaviors[contract_no]

        # More DPD = more interactions
        if dpd_current == 0:
            num_interactions = random.choices([0, 1, 2], weights=[0.70, 0.20, 0.10])[0]
        elif dpd_current <= 15:
            num_interactions = random.choices([1, 2, 3], weights=[0.50, 0.35, 0.15])[0]
        elif dpd_current <= 45:
            num_interactions = random.choices([2, 3, 4, 5], weights=[0.30, 0.40, 0.20, 0.10])[0]
        else:
            num_interactions = random.choices([4, 5, 6, 8], weights=[0.25, 0.35, 0.25, 0.15])[0]

        for i in range(num_interactions):
            action_date = datetime.now() - timedelta(days=max(1, dpd_current - random.randint(0, 20)))

            # Treatment escalation: WA -> Deskcoll -> Visit -> Somasi
            if dpd_current <= 15:
                treatment = random.choices(['WA', 'SMS', 'Deskcoll'], weights=[0.60, 0.25, 0.15])[0]
            elif dpd_current <= 45:
                treatment = random.choices(['Deskcoll', 'WA', 'Visit'], weights=[0.50, 0.25, 0.25])[0]
            else:
                treatment = random.choices(['Visit', 'Somasi', 'Pickup'], weights=[0.35, 0.40, 0.25])[0]

            # Result probability based on actual default tendency
            if will_default:
                # Defaulters mostly refuse or avoid
                result = random.choices(
                    ['Menolak', 'Rumah Kosong', 'PTP', 'Bayar'],
                    weights=[0.50, 0.25, 0.15, 0.10]
                )[0]
            else:
                # Payers mostly pay or promise
                result = random.choices(
                    ['Bayar', 'PTP', 'Menolak', 'Rumah Kosong'],
                    weights=[0.50, 0.30, 0.12, 0.08]
                )[0]

            promise_date = action_date + timedelta(days=random.randint(3, 14)) if result == 'PTP' else None

            # Interaction score
            if result == 'Bayar':
                int_score = random.choice([4, 5])
            elif result == 'PTP':
                int_score = random.choice([3, 4])
            elif result == 'Rumah Kosong':
                int_score = 1
            else:  # Menolak
                int_score = random.choice([1, 2])

            data.append({
                'LKP_ID': f"LKP-{lkp_id_counter:06d}",
                'CONTRACT_NO': contract_no,
                'ACTION_DATE': action_date.strftime('%Y-%m-%d'),
                'TREATMENT_TYPE': treatment,
                'RESULT_CODE': result,
                'PROMISE_DATE': promise_date.strftime('%Y-%m-%d') if promise_date else '',
                'COLLECTOR_ID': f"COLL-{random.randint(1, 50):03d}",
                'INTERACTION_SCORE': int_score,
            })
            lkp_id_counter += 1

    return pd.DataFrame(data)


# ==========================================
# MAIN GENERATION
# ==========================================

# Generate all tables
df_customer, customer_true_defaults = generate_customer_master(NUM_CUSTOMERS)
df_contract, contract_default_probs = generate_contract_snapshot(df_customer, customer_true_defaults)
df_payment, contract_behaviors = generate_payment_history(df_contract, contract_default_probs)
df_lkp = generate_lkp_history(df_contract, contract_default_probs, contract_behaviors)

# Statistics
paid_count = len(df_payment[df_payment['PAY_STATUS'].isin(['Full', 'Overpaid'])])
partial_count = len(df_payment[df_payment['PAY_STATUS'] == 'Partial'])
print(f"\n✓ Customers: {len(df_customer)}")
print(f"✓ Contracts: {len(df_contract)}")
print(f"✓ Payment records: {len(df_payment)}")
print(f"  - Full/Overpaid: {paid_count} ({100*paid_count/len(df_payment):.1f}%)")
print(f"  - Partial: {partial_count} ({100*partial_count/len(df_payment):.1f}%)")
print(f"✓ LKP interactions: {len(df_lkp)}")

# Export to Excel
print("\nSaving to Excel...")
excel_filename = "Dataset_CollectAI_Realistic.xlsx"
with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
    df_customer.to_excel(writer, sheet_name='1_Customer_Master', index=False)
    df_contract.to_excel(writer, sheet_name='2_Contract_Snapshot', index=False)
    df_payment.to_excel(writer, sheet_name='3_Payment_History', index=False)
    df_lkp.to_excel(writer, sheet_name='4_LKP_Interaction', index=False)

print(f"✓ Saved to {excel_filename}")

# Export to PostgreSQL
print("\nSaving to PostgreSQL...")
db_tables = {
    'customer_master': df_customer,
    'contract_snapshot': df_contract,
    'payment_history': df_payment,
    'lkp_interaction': df_lkp,
}
append_dataframes_to_postgres(db_tables, if_exists='replace')  # Replace to get clean data
print("✓ Data loaded to PostgreSQL\n")
