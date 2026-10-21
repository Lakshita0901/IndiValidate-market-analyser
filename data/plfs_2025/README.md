# PLFS 2025 Data Directory

This directory contains the official data files from the **Periodic Labour Force Survey (PLFS) Annual Report 2025**.

**Official Source:**
Ministry of Statistics and Programme Implementation (MoSPI)
PLFS Annual Report 2025 (January–December 2025)
URL: https://www.mospi.gov.in

---

## How to Set Up

1. **Download the PLFS 2025 Annual Report** from:
   https://www.mospi.gov.in (Publications & Reports → PLFS 2025 Annual Report)

2. **Open the Annual Report** PDF or Excel file.

3. **For each table listed below**, copy the data into a CSV file with:
   - First column: State/UT name
   - Remaining columns: the numeric indicators (Total, Rural, Urban, or sub-categories)

4. **Save the CSV files** in this directory with the exact names listed below.

---

## Required Files

| File Name       | PLFS Table | Description                                      |
|----------------|-----------|--------------------------------------------------|
| `table_22.csv`  | Table 22  | LFPR by education level and State/UT             |
| `table_23.csv`  | Table 23  | WPR by education level and State/UT              |
| `table_24.csv`  | Table 24  | Unemployment Rate by education and State/UT      |
| `table_25.csv`  | Table 25  | % distribution of workers by occupation (NCO)   |
| `table_26.csv`  | Table 26  | % distribution of workers by industry (NIC)     |
| `table_27.csv`  | Table 27  | Industry distribution by State/UT               |
| `table_34.csv`  | Table 34  | Employment status by State/UT                    |
| `table_38.csv`  | Table 38  | Average wage/salary (regular salaried) by State |
| `table_39.csv`  | Table 39  | Average wage earnings (casual labour) by State  |
| `table_40.csv`  | Table 40  | Average gross earnings (self-employed) by State |

---

## Expected CSV Format

### For LFPR/WPR/UR tables (Table 22, 23, 24):
```
State/UT,Total,Rural,Urban
Andhra Pradesh,45.2,44.1,48.3
Assam,56.7,57.2,54.1
...
```

### For wage tables (Table 38, 39, 40):
```
State/UT,Total,Rural,Urban
Andhra Pradesh,18500,15200,22100
Assam,14200,12100,18800
...
```

### For employment status (Table 34):
```
State/UT,Self-employed,Regular Salaried,Casual Labour
Andhra Pradesh,55.3,28.1,16.6
...
```

---

## Important Notes

1. **AGGREGATE DATA ONLY**: These tables contain state/UT level aggregate statistics.
   They do NOT contain individual or household-level data.

2. **CORRECT interpretation**: 
   "PLFS 2025 reports that the aggregate average monthly wage/salary for regular
   salaried workers in Maharashtra is ₹X."

3. **WRONG interpretation**:
   "A person in Maharashtra earns ₹X per month."

4. **Year**: All PLFS 2025 data covers the period January–December 2025.

5. **Methodology change**: PLFS 2025 uses a revised sampling methodology compared
   to earlier surveys. Do not directly compare with pre-2025 PLFS data.

---

## If Files Are Missing

If the CSV files are not present, the `plfs_tool.py` will:
- Return a clear error message (NOT fake data)
- Explain exactly which files are needed and where to get them
- Allow the Reddit, Google Trends, and Census tools to continue running

The system will NOT fabricate PLFS values if the files are missing.
