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


PRODUCT_INTEREST_RATE_RANGE = {
    # Rate tahunan ilustratif per PRODUCT_TYPE (dipakai restructuring engine
    # untuk hitung amortisasi/haircut — BUKAN fitur model scoring, lihat
    # collect-ai-upgrade.md). Perlu di-review tim finance sebelum production.
    'Motor': (0.18, 0.30),
    'Elektronik & Furnitur': (0.20, 0.36),
    'Haji & Umrah': (0.12, 0.20),
    'Dana Tunai': (0.24, 0.40),
    'Modal Usaha': (0.15, 0.24),
}


def assign_interest_rate(product_type):
    """Rate tahunan (decimal) untuk satu kontrak, acak dalam rentang wajar
    per PRODUCT_TYPE. Independen dari default_prob — rate ditentukan saat
    origination oleh kebijakan produk, bukan oleh perilaku bayar nasabah."""
    low, high = PRODUCT_INTEREST_RATE_RANGE.get(product_type, (0.18, 0.30))
    return round(random.uniform(low, high), 4)


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
CYCLE_ENCODE = {'C0': 0, 'C1': 1, 'C2': 2, 'C3+': 3}
CYCLE_DECODE = {0: 'C0', 1: 'C1', 2: 'C2', 3: 'C3+'}


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

            ambc = round(prnc * random.uniform(0.05, 0.20), 2) if dpd > 0 else 0.0
            installment = round(prnc * random.uniform(0.02, 0.10), 2)

            # Repayment progress: nasabah dengan default_prob rendah sudah
            # melunasi porsi lebih besar dari pinjamannya (recovery_ratio tinggi
            # secara nyata, bukan angka acak), dan karena itu tenor yang sudah
            # dijalani lebih panjang -> MATURITY_DATE lebih dekat.
            total_ots_now = prnc + round(prnc * 0.10, 2)
            progress = float(np.clip(
                (1 - cust_default_prob) * random.uniform(0.5, 1.0) + random.uniform(-0.05, 0.05),
                0.05, 0.95,
            ))
            loan_amount = round(total_ots_now / (1 - progress), 2)

            tenor_months = random.randint(12, 60)
            elapsed_months = min(tenor_months - 1, max(0, progress * tenor_months * random.uniform(0.85, 1.15)))
            remaining_days = max(30, int((tenor_months - elapsed_months) * 30))
            maturity = datetime.now() + timedelta(days=remaining_days)

            # PREV_CYCLE: arah perubahan cycle bulan lalu dipengaruhi
            # default_prob nasabah (risiko tinggi -> cenderung memburuk/stabil,
            # risiko rendah -> cenderung stabil/membaik), bukan acak murni.
            if cust_default_prob >= 0.5:
                direction_weights = [0.45, 0.40, 0.15]   # worsen, stable, improve
            elif cust_default_prob >= 0.25:
                direction_weights = [0.25, 0.50, 0.25]
            else:
                direction_weights = [0.10, 0.45, 0.45]
            cycle_direction_seed = random.choices([1, 0, -1], weights=direction_weights)[0]
            prev_cycle_encoded = max(0, min(3, CYCLE_ENCODE[cycle] - cycle_direction_seed))
            prev_cycle = CYCLE_DECODE[prev_cycle_encoded]

            product_type = random.choice(['Motor', 'Elektronik & Furnitur', 'Haji & Umrah', 'Dana Tunai', 'Modal Usaha'])

            data.append({
                'CONTRACT_NO': contract_no,
                'CUST_ID': cust_id,
                'DPD_CURRENT': dpd,
                'PRNC_OTS': prnc,
                'INTR_OTS': round(prnc * 0.10, 2),
                'CYCLE': cycle,
                'PRODUCT_TYPE': product_type,
                'INTEREST_RATE': assign_interest_rate(product_type),
                'AMBC': ambc,
                'PREV_CYCLE': prev_cycle,
                'LOAN_AMOUNT': loan_amount,
                'INSTALLMENT_AMOUNT': installment,
                'MATURITY_DATE': maturity.strftime('%Y-%m-%d'),
                'OVERDUE_INSTALLMENT_COUNT': max(0, int(dpd / 30)),
                'LATE_FEE_AMOUNT': round(dpd * 10000.0, 2)
            })
    return pd.DataFrame(data), contract_default_probs


def decide_contract_behaviors(contract_default_probs):
    """Tentukan SEKALI di awal apakah tiap kontrak akhirnya akan default atau
    tidak. Dipakai bersama oleh LKP dan payment history supaya kedua tabel
    konsisten dengan satu 'nasib' nasabah yang sama (bukan digambar ulang
    secara independen di masing-masing generator)."""
    return {
        contract_no: (random.random() < prob)
        for contract_no, prob in contract_default_probs.items()
    }


# ==========================================
# 3. PAYMENT HISTORY (KEY: Sticky Behavior)
# ==========================================
def generate_payment_history(df_contr, contract_default_probs, contract_behaviors, lkp_lookup=None):
    """
    Payment history follows customer's default probability with STICKY BEHAVIOR.
    Once a customer establishes pattern (payer/defaulter), they mostly maintain it.

    ``lkp_lookup``: dict {CONTRACT_NO: [(action_date, treatment_type), ...]}
    (terurut naik berdasarkan tanggal) dari LKP interaction yang SUDAH
    dibuat sebelumnya, dipakai supaya RECOVERY_SOURCE mencerminkan channel
    yang benar-benar berinteraksi dengan nasabah sebelum ia bayar — bukan
    dipilih acak tanpa hubungan dengan lkp_interaction.
    """
    lkp_lookup = lkp_lookup or {}
    TREATMENT_TO_SOURCE = {
        'WA': 'WA', 'SMS': 'SMS', 'Deskcoll': 'Deskcoll',
        'Visit': 'Visit', 'Somasi': 'Somasi', 'Pickup': 'Somasi',
    }

    def _pick_recovery_source(contract_no, pay_date, will_default):
        history = lkp_lookup.get(contract_no)
        if history:
            # Treatment terakhir yang terjadi SEBELUM/pada tanggal pembayaran
            prior = [t for d, t in history if d <= pay_date]
            if prior:
                return TREATMENT_TO_SOURCE.get(prior[-1], 'Deskcoll')
            # Belum ada interaksi sebelum bayar — pakai yang paling awal
            return TREATMENT_TO_SOURCE.get(history[0][1], 'Deskcoll')
        # Tidak ada LKP sama sekali untuk kontrak ini — fallback proporsional
        # dengan tingkat keparahan (bukan uniform 5 channel).
        if will_default:
            return random.choices(['Visit', 'Somasi'], weights=[0.55, 0.45])[0]
        return random.choices(['WA', 'SMS', 'Deskcoll'], weights=[0.5, 0.2, 0.3])[0]

    data = []
    pay_id_counter = 1

    for index, row in df_contr.iterrows():
        contract_no = row['CONTRACT_NO']
        dpd_current = row['DPD_CURRENT']
        prnc_ots = row['PRNC_OTS']

        num_payments = random.randint(6, 18)
        base_due_date = datetime.now() - timedelta(days=30 * num_payments)

        # Perilaku (akan default atau tidak) sudah ditentukan sebelumnya dan
        # dibagi bersama dengan LKP generator — lihat decide_contract_behaviors().
        will_eventually_default = contract_behaviors[contract_no]

        # Behavior consistency: probabilitas historic payment "on track"
        # ditentukan SEKALI per kontrak (bukan tiap bulan) supaya konsisten
        # dengan will_eventually_default, dan benar-benar berkorelasi dengan
        # risiko nasabah (sebelumnya formula lama bisa > 1.0 sehingga hampir
        # semua histori jadi "Full" apapun default_prob-nya).
        if will_eventually_default:
            historic_pay_prob = random.uniform(0.10, 0.40)
        else:
            historic_pay_prob = random.uniform(0.75, 0.97)
        est_installment = max(500000, round(prnc_ots / max(1, num_payments)))

        for i in range(num_payments):
            due_date = base_due_date + timedelta(days=30 * i)

            # Determine if payment for THIS month
            if i < num_payments - 1:
                # Historic payments: sticky terhadap will_eventually_default
                should_pay = random.random() < historic_pay_prob
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

            # Self-cure logic: high chance if delay is small, low if large
            self_cure = True if delay <= 7 else random.random() < 0.20

            # Recovery source: only applies if not self-cured. Diambil dari
            # treatment LKP yang benar-benar mendahului pembayaran ini.
            recovery_source = None if self_cure else _pick_recovery_source(
                contract_no, actual_pay_date, will_eventually_default
            )

            data.append({
                'PAYMENT_ID': f"PAY-{pay_id_counter:07d}",
                'CONTRACT_NO': contract_no,
                'DUE_DATE': due_date.strftime('%Y-%m-%d'),
                'ACTUAL_PAY_DATE': actual_pay_date.strftime('%Y-%m-%d'),
                'PAYMENT_AMOUNT': pay_amount,
                'PAY_STATUS': pay_status,
                'PAY_METHOD': random.choice(['Autodebet', 'VA', 'Kasir', 'Transfer Bank', 'COD']),
                'DELAY_DAYS': max(0, delay),
                'SELF_CURE_FLAG': self_cure,
                'RECOVERY_SOURCE': recovery_source
            })
            pay_id_counter += 1

    return pd.DataFrame(data)


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
        ambc_val = row.get('AMBC', 0) or (row['PRNC_OTS'] * 0.10)

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

            if result == 'Bayar':
                int_score = random.choice([4, 5])
                contact_success = True
                rpc = True
            elif result == 'PTP':
                int_score = random.choice([3, 4])
                contact_success = True
                rpc = True
            elif result == 'Rumah Kosong':
                int_score = 1
                contact_success = False
                rpc = False
            else:  # Menolak
                int_score = random.choice([1, 2])
                contact_success = True
                rpc = random.choice([True, False])

            # PTP specific fields
            if result == 'PTP':
                # Coverage ratio: nasabah yang benar-benar akan bayar cenderung
                # berjanji mendekati/melebihi AMBC; yang akan default cenderung
                # berjanji jumlah kecil (token promise) — bukan angka acak
                # yang lepas dari AMBC.
                if will_default:
                    coverage = random.uniform(0.10, 0.55)
                else:
                    coverage = random.uniform(0.70, 1.30)
                ptp_amt = round(max(100000.0, ambc_val * coverage), 2)
                # simulate if it's already kept, broken, or open based on promise_date
                if promise_date and promise_date < datetime.now():
                    ptp_stat = 'KEPT' if not will_default else 'BROKEN'
                else:
                    ptp_stat = 'OPEN'
            else:
                ptp_amt = None
                ptp_stat = None

            data.append({
                'LKP_ID': f"LKP-{lkp_id_counter:06d}",
                'CONTRACT_NO': contract_no,
                'ACTION_DATE': action_date.strftime('%Y-%m-%d'),
                'TREATMENT_TYPE': treatment,
                'RESULT_CODE': result,
                'PROMISE_DATE': promise_date.strftime('%Y-%m-%d') if promise_date else '',
                'COLLECTOR_ID': f"COLL-{random.randint(1, 50):03d}",
                'INTERACTION_SCORE': int_score,
                'PTP_AMOUNT': ptp_amt,
                'PTP_STATUS': ptp_stat,
                'RPC_FLAG': rpc,
                'CONTACT_SUCCESS_FLAG': contact_success,
            })
            lkp_id_counter += 1

    return pd.DataFrame(data)


# ==========================================
# MAIN GENERATION
# ==========================================

# Generate all tables
df_customer, customer_true_defaults = generate_customer_master(NUM_CUSTOMERS)
df_contract, contract_default_probs = generate_contract_snapshot(df_customer, customer_true_defaults)

# Nasib akhir tiap kontrak (bayar vs default) ditentukan SEKALI di sini agar
# LKP dan payment history konsisten satu sama lain (bukan digambar ulang
# secara independen di masing-masing generator).
contract_behaviors = decide_contract_behaviors(contract_default_probs)

# LKP dibuat lebih dulu supaya RECOVERY_SOURCE di payment history bisa
# merujuk ke treatment yang benar-benar terjadi sebelum pembayaran.
df_lkp = generate_lkp_history(df_contract, contract_default_probs, contract_behaviors)

lkp_lookup = {}
if not df_lkp.empty:
    lkp_sorted = df_lkp.sort_values('ACTION_DATE')
    for contract_no, grp in lkp_sorted.groupby('CONTRACT_NO'):
        lkp_lookup[contract_no] = list(zip(
            pd.to_datetime(grp['ACTION_DATE']), grp['TREATMENT_TYPE']
        ))

df_payment = generate_payment_history(df_contract, contract_default_probs, contract_behaviors, lkp_lookup)

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
append_dataframes_to_postgres(db_tables, if_exists='append')  # Append to preserve schema constraints
print("✓ Data loaded to PostgreSQL\n")
