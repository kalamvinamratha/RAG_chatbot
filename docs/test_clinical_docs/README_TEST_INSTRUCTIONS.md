# 🏥 Clinical Test Documents & Validation Guide

These sample documents are ready for uploading into the **Healthcare AI Hybrid Graph RAG** web application to test domain-specific agents.

---

## 📁 Available Test Documents

| Domain / Agent       | Formats Available       | Primary File                                    | Key Clinical Topics                                                                                                                   |
| :------------------- | :---------------------- | :---------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------ |
| **Cardiology**       | `.pdf`, `.docx`, `.txt` | `Cardiology_Atrial_Fibrillation_Guidelines.pdf` | Atrial Fibrillation, CHA2DS2-VASc scoring, DOAC dosing (Apixaban, Rivaroxaban, Dabigatran), Rate control (Metoprolol, Diltiazem)      |
| **Neurology**        | `.pdf`, `.docx`, `.txt` | `Neurology_Acute_Ischemic_Stroke_Protocol.pdf`  | Acute Ischemic Stroke, NIHSS scale, Thrombolytic therapy (Tenecteplase vs Alteplase), Blood pressure targets, Mechanical thrombectomy |
| **General Medicine** | `.pdf`, `.docx`         | `GeneralMedicine_Type2_Diabetes_Protocol.pdf`   | Type 2 Diabetes, Metformin renal thresholds, SGLT2 inhibitors (Empagliflozin), GLP-1 RA (Semaglutide), Statin therapy                 |

All files are located in:  
`./docs/test_clinical_docs/`

---

## 🧪 Testing Agent 1: Cardiology Specialist

### Step 1: Upload Document

1. Open the web app in your browser (`http://localhost:5173`).
2. In the top navigation or sidebar, select the **Cardiology** agent (Heart icon).
3. In the **Document Upload** dropzone, drag and drop or browse to:
   `test_clinical_docs/Cardiology_Atrial_Fibrillation_Guidelines.pdf`
4. Wait a few seconds for ingestion (chunks created, vectors indexed in Qdrant, entities extracted to Neo4j).

### Step 2: Test Prompts to Ask

#### Query 1: DOAC Dose Adjustment

> **Prompt:**  
> _"What is the recommended dose of Apixaban for an 82-year-old patient weighing 58 kg with non-valvular atrial fibrillation?"_

- **Expected Response:**
  - Identifies that standard dose is 5 mg PO BID, but this patient meets two ABC dose-reduction criteria (Age ≥ 80 and Weight ≤ 60 kg), so the adjusted dose is **2.5 mg PO twice daily**.
- **Evidence Inspector Verification:**
  - **Passages Tab:** Displays citations with Page 1/2 of the guideline with high match scores.
  - **Keywords Tab:** Highlights `Apixaban` (Medication), `82-year-old` (Clinical Term), `Atrial Fibrillation` (Condition).
  - **Knowledge Graph Tab:** Shows relational nodes: `[Apixaban] ──[TREATS]──► [Atrial Fibrillation]`.

#### Query 2: First-Line Rate Control

> **Prompt:**  
> _"What are the first-line pharmacologic agents for rate control in hemodynamically stable atrial fibrillation, and what is the target resting heart rate?"_

- **Expected Response:**
  - Highlights Beta-Blockers (Metoprolol succinate, Bisoprolol, Carvedilol) and Non-DHP CCBs (Diltiazem, Verapamil).
  - Resting heart rate target < 110 bpm (lenient control) or < 80 bpm if symptomatic.

---

## 🧪 Testing Agent 2: Neurology Specialist

### Step 1: Upload Document

1. In the Agent Selector, switch to the **Neurology** agent (Brain icon).
2. Drag and drop:
   `test_clinical_docs/Neurology_Acute_Ischemic_Stroke_Protocol.pdf`
3. Confirm upload status badge displays green / ingested.

### Step 2: Test Prompts to Ask

#### Query 1: Thrombolytic Dosing & Window

> **Prompt:**  
> _"What is the time window and dosing for Tenecteplase in acute ischemic stroke, and how does it compare to Alteplase?"_

- **Expected Response:**
  - Time window: Within 4.5 hours of symptom onset.
  - Tenecteplase dosing: **0.25 mg/kg IV single bolus over 5 seconds (max 25 mg)** without infusion pump.
  - Alteplase comparison: 0.9 mg/kg total (10% bolus over 1 min, 90% over 60 mins).
- **Evidence Inspector Verification:**
  - **Passages Tab:** Direct citation to Section 3 of the Acute Stroke protocol.
  - **Keywords Tab:** Highlights `Tenecteplase` (Medication), `Alteplase` (Medication), `Stroke` (Condition).
  - **Knowledge Graph Tab:** Shows `[Tenecteplase] ──[TREATS]──► [Acute Ischemic Stroke]`.

#### Query 2: Strict Blood Pressure Targets

> **Prompt:**  
> _"What blood pressure targets must be achieved before and maintained after intravenous thrombolysis in acute stroke?"_

- **Expected Response:**
  - Pre-thrombolysis: **Systolic < 185 mmHg** and **Diastolic < 110 mmHg** (managed with IV Labetalol or Nicardipine).
  - Post-thrombolysis: **< 180/105 mmHg** for at least 24 hours.
