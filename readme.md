Data Analysis Using PySpark & Apache Spark in Databricks

Overview

This project focuses on analyzing sales and menu data using PySpark in Databricks. The dataset is loaded from CSV files, transformed as per business requirements, and used to generate key insights with visualizations in a Databricks Dashboard.

Data Sources

Sales Data (sales.csv)

Menu Data (menu.csv)

Schema

Sales Schema

Column

Data Type

product_id

Integer

customer_id

String

order_date

Date

location

String

source_order

String

Menu Schema

Column

Data Type

product_id

Integer

product_name

String

price

String

Key Data Transformations

Extracted year, month, and quarter from order_date.

Joined sales and menu data to calculate revenue and customer insights.

Grouped data by various attributes for detailed analysis.

Analysis & Insights

1. Total Amount Spent By Each Customer

Calculates the total spending per customer.

2. Total Amount Spent By Each Food Category

Aggregates total sales by different food categories.

3. Total Amount Spent Each Month

Monthly spending trends analysis.

4. Yearly & Quarterly Sales

Annual and quarterly revenue tracking.

5. Total Number of Orders By Each Category

Identifies the popularity of different food categories.

6. Top Ordered Item

Finds the most frequently ordered product.

7. Customer Visit Frequency

Analyzes repeat customer visits.

8. Total Sales By Each Country

Breakdown of sales by customer location.

9. Total Sales By Order Source

Examines sales trends based on ordering platforms.

Dashboard

A Databricks Dashboard was created to visualize these insights using:

Bar Charts

Line Charts

Pie Charts

How to Run the Project

Prerequisites

Databricks Community Edition (or an active Databricks workspace)

PySpark Installed (pip install pyspark)

Steps

Upload the dataset to Databricks FileStore.

Open the Jupyter Notebook in Databricks.

Execute the notebook cells to process the data.

View the generated dashboard for insights.

File Structure

📁 Project Folder
│── Data-Analysis.ipynb  # Jupyter Notebook with PySpark analysis
│── sales.csv            # Sales dataset
│── menu.csv             # Menu dataset
│── README.md            # Project documentation

Future Enhancements

Integrate real-time data streaming using Apache Kafka.

Add machine learning models for sales prediction.

Improve dashboard UI with more interactive elements.