-- bronze.transactions keeps full history (for opening dates); the analysis uses the slice
SELECT date, store_nbr, transactions AS receipts
FROM bronze.transactions
WHERE date >= DATE '$slice_start'
