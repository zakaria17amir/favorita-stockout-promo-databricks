# Sales & Menu Data Analysis — PySpark & Apache Spark

Large-scale sales data analysis using PySpark in Databricks — covering revenue trends, customer behaviour, and product performance with interactive dashboard visualisations.

---

## 📌 Overview

This project demonstrates big data processing using Apache Spark via PySpark in a Databricks environment. Sales and menu data are loaded from CSV files, transformed through a series of business-logic driven queries, and visualised in a Databricks Dashboard.

The analysis answers real business questions: who spends the most, which products drive revenue, and how do sales vary by time, location, and channel?

---

## 🛠 Tech Stack

![PySpark](https://img.shields.io/badge/PySpark-E25A1C?style=flat&logo=apachespark&logoColor=white)
![Databricks](https://img.shields.io/badge/Databricks-FF3621?style=flat&logo=databricks&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?style=flat&logo=mysql&logoColor=white)

---

## 📊 Data Sources

**Sales (`sales.csv`)**

| Column | Type |
|---|---|
| product_id | Integer |
| customer_id | String |
| order_date | Date |
| location | String |
| source_order | String |

**Menu (`menu.csv`)**

| Column | Type |
|---|---|
| product_id | Integer |
| product_name | String |
| price | String |

---

## 🔍 Key Analyses

| Analysis | Description |
|---|---|
| Total spend per customer | Revenue contribution by individual customer |
| Spend by food category | Which product categories drive the most revenue |
| Monthly spending trends | Time-series revenue patterns by month |
| Yearly & quarterly sales | Annual and quarterly aggregates |
| Orders by category | Popularity ranking of food categories |
| Top ordered item | Most frequently purchased product |
| Customer visit frequency | Repeat purchase behaviour |
| Sales by country | Geographic revenue breakdown |
| Sales by order source | Channel performance (in-store, app, etc.) |

---

## 📁 Project Structure

```
Sales-Menu-Analysis/
├── Data-Analysis.ipynb   # Main PySpark notebook
├── sales.csv             # Sales dataset
├── menu.csv              # Menu dataset
└── README.md
```

---

## 🚀 How to Run

**Prerequisites:** Databricks account (Community Edition works) or local PySpark setup

```bash
# For local setup
pip install pyspark

# Then open the notebook in Jupyter or upload to Databricks
jupyter notebook Data-Analysis.ipynb
```

**On Databricks:**
1. Upload `sales.csv` and `menu.csv` to Databricks FileStore
2. Import `Data-Analysis.ipynb` into your workspace
3. Run all cells
4. Open the generated Dashboard to view visualisations

---

## 🔮 Future Enhancements

- Add real-time data streaming via Apache Kafka
- Build a sales forecasting model using Spark MLlib
- Improve dashboard interactivity with Databricks SQL
