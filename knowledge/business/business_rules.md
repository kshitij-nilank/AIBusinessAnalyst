# Parcon Business Rules

## FYear Rule
```sql
CASE 
  WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season 
  ELSE 0 
END AS FYear
```

Always filter out invalid years:
```sql
HAVING FYear <> 0
```

## SaleAlias Rule
```sql
IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) AS SaleAlies
```

## AreaAlias Rule
```sql
CASE 
  WHEN Area IN ("AS") AND Centre IN ("KOL","GUW") THEN "AS"
  WHEN Area IN ("DO","TR") AND Centre IN ("KOL","SIL") THEN "DO/TR"
  WHEN Area IN ("CA","TP") AND Centre IN ("KOL","GUW") THEN "CA/TP"
  ELSE "OTHERS"
END AS AreaAlies
```

## Standard Measures

### Offer Quantity
```sql
COALESCE(SUM(IF(LotStatus = 'Sold', TotalWeight, InvoiceWeight))) AS Offer_Qty
```

### Sold Quantity
```sql
COALESCE(SUM(TotalWeight)) AS Sold_Qty
```

### Total Value
```sql
COALESCE(SUM(Value)) AS Total_Value
```

### Average Price
```sql
ROUND(SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)), 2) AS Avg_Price
```

## Common Filters
- Category: CTC / ORTHODOX
- EstBlf: EST / BLF
- Area: AS / DO / TR / CA / TP
- Centre: KOL / GUW / SIL
