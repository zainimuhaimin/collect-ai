import pandas as pd
import json

print("Membaca file Dataset_CollectAI_Dummy.xlsx...")

# 1. Load Data dari Excel
df_cust = pd.read_excel("Dataset_CollectAI_Dummy.xlsx", sheet_name="1_Customer_Master")
df_contr = pd.read_excel("Dataset_CollectAI_Dummy.xlsx", sheet_name="2_Contract_Snapshot")
df_pay = pd.read_excel("Dataset_CollectAI_Dummy.xlsx", sheet_name="3_Payment_History")
df_lkp = pd.read_excel("Dataset_CollectAI_Dummy.xlsx", sheet_name="4_LKP_Interaction")
df_ai = pd.read_excel("Dataset_CollectAI_Dummy.xlsx", sheet_name="5_AI_Intelligence")

jsonl_data = []

print("Memproses dan merakit narasi LLM...")

# 2. Iterasi setiap kontrak untuk merakit Prompt (Input & Output)
for index, contr in df_contr.iterrows():
    contract_no = contr['CONTRACT_NO']
    cust_id = contr['CUST_ID']
    
    # Ambil data Master
    cust_info = df_cust[df_cust['CUST_ID'] == cust_id].iloc[0]
    
    # Ambil data AI Output (Hasil perhitungan Machine Learning Layer 1)
    ai_info = df_ai[df_ai['CONTRACT_NO'] == contract_no].iloc[0]
    rec_score = ai_info['RECOVERY_SCORE']
    risk_seg = ai_info['RISK_SEGMENT']
    nba = ai_info['NBA_RECOMMENDATION']
    priority = ai_info['PRIORITY_LEVEL']
    
    # Ambil Rata-rata telat bayar (Delay Days)
    pay_history = df_pay[df_pay['CONTRACT_NO'] == contract_no]
    avg_delay = int(pay_history['DELAY_DAYS'].mean()) if not pay_history.empty else 0
    
    # Ambil Interaksi Terakhir (LKP)
    lkp_history = df_lkp[df_lkp['CONTRACT_NO'] == contract_no]
    if not lkp_history.empty:
        # Sortir by action_date terbaru
        last_lkp = lkp_history.sort_values(by='ACTION_DATE', ascending=False).iloc[0]
        last_result = last_lkp['RESULT_CODE']
        last_score = last_lkp['INTERACTION_SCORE']
    else:
        last_result = "Belum ada interaksi"
        last_score = 0
        
    # ==========================================
    # RULE BASED NARRATIVE GENERATOR (Untuk mengajari LLM logikanya)
    # ==========================================
    narasi = ""
    
    # Rule 1: Self-cure (Skor ML Tinggi, DPD Rendah)
    if risk_seg == 'Self-cure':
        narasi = f"Nasabah tergolong Self-cure. Sisa pokok masih Rp {contr['PRNC_OTS']:,.0f} namun DPD hanya {contr['DPD_CURRENT']} hari. "
        narasi += f"Secara historis nasabah rata-rata telat {avg_delay} hari saja. Dengan Machine Learning Recovery Score {rec_score:.2f}, probabilitas bayar mandiri sangat tinggi. "
        narasi += f"Tindakan terbaik adalah {nba} sebagai pengingat ringan otomatis."
        
    # Rule 2: Can Pay (Mampu bayar tapi butuh didorong)
    elif risk_seg == 'Can Pay':
        narasi = f"Nasabah masuk kategori Can Pay dengan DPD {contr['DPD_CURRENT']} hari. "
        narasi += f"Interaksi terakhir menunjukkan hasil '{last_result}' dengan skor kooperatif {last_score}/5. "
        narasi += f"Meskipun ada tunggakan, ML Recovery Score menunjukkan angka {rec_score:.2f}. "
        if nba == 'Visit':
            narasi += "Nasabah kurang responsif jika hanya ditagih online, sehingga kunjungan fisik (Visit) adalah tindakan paling efektif bulan ini."
        else:
            narasi += f"Pendekatan via {nba} dengan prioritas {priority} disarankan untuk memicu pembayaran."
            
    # Rule 3: Cannot Pay (Tidak mampu, tapi mungkin itikad baik)
    elif risk_seg == 'Cannot Pay':
        narasi = f"Perhatian: Nasabah Cannot Pay. Sisa utang cukup besar (Rp {contr['PRNC_OTS']:,.0f}) dengan tingkat pendapatan {cust_info['CUST_INCOME_LEVEL']}. "
        narasi += f"DPD sudah mencapai {contr['DPD_CURRENT']} hari (Cycle {contr['CYCLE_AKHIR']}). "
        if last_result == 'PTP':
            narasi += f"Nasabah memiliki itikad baik (janji bayar), namun ML memprediksi probabilitas nyata hanya {rec_score:.2f}. "
            narasi += f"Tindakan {nba} diperlukan untuk memastikan janji bayar ditepati."
        else:
            narasi += f"Diperlukan eskalasi {nba} segera mengingat histori pembayaran yang sering tertunda rata-rata {avg_delay} hari."
            
    # Rule 4: Won't Pay (Menolak / Susah ditagih)
    else:
        narasi = f"Nasabah Kritis (Won't Pay). DPD berada di angka {contr['DPD_CURRENT']} hari. "
        narasi += f"Catatan lapangan menunjukkan interaksi terakhir '{last_result}' (Skor {last_score}/5). "
        narasi += f"Recovery Score ML sangat rendah ({rec_score:.2f}), menunjukkan keengganan membayar. "
        narasi += f"Jangan buang waktu dengan WA/SMS. Segera lakukan {nba} untuk mengamankan aset perusahaan."

    # ==========================================
    # PEMBENTUKAN FORMAT JSONL (ALPACA FORMAT)
    # ==========================================
    instruction = "Analisis profil nasabah ini, tentukan Risk Segment, Prioritas, Next Best Action (NBA), dan berikan narasi panduan strategis untuk collector."
    
    input_text = f"Data Profil: Usia {cust_info['CUST_AGE']} thn, Pekerjaan: {cust_info['CUST_OCCUPATION']}, Pendapatan: {cust_info['CUST_INCOME_LEVEL']}. "
    input_text += f"Kondisi Kontrak: DPD {contr['DPD_CURRENT']} hari ({contr['CYCLE_AKHIR']}), Sisa Pokok: Rp {contr['PRNC_OTS']:,.0f}. "
    input_text += f"Histori: Rata-rata telat {avg_delay} hari, Hasil Interaksi Terakhir: {last_result} (Score {last_score}/5). "
    input_text += f"[ML Recovery Score: {rec_score:.2f}]"
    
    output_text = f"Risk Segment: {risk_seg}\n"
    output_text += f"Prioritas: {priority}\n"
    output_text += f"Next Best Action: {nba}\n\n"
    output_text += f"Narasi Analisis:\n{narasi}"
    
    jsonl_data.append({
        "instruction": instruction,
        "input": input_text,
        "output": output_text
    })

# 3. Export ke file .jsonl
with open("dataset_kredit.jsonl", "w", encoding="utf-8") as f:
    for item in jsonl_data:
        f.write(json.dumps(item) + "\n")

print(f"Berhasil! File dataset_kredit.jsonl siap digunakan untuk Fine-Tuning Llama.")