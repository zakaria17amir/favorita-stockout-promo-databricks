SELECT item_nbr AS item_key, item_nbr, family, class, perishable = 1 AS is_perishable
FROM bronze.items
