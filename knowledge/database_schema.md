# Database Schema Reference

Source files analyzed:
- `knowledge/SQL UTILITY.sql`
- `knowledge/Usage Pattern Indexing.sql`

This document only includes information visible in the analyzed SQL files. If a purpose, join, filter, calculation, or usage pattern is not shown in those files, it is marked as `Unknown`.

## `data-warehousing-prod.EasyReports.SaleTransactionView`

### Purpose
Auction sale transaction reporting. Used for auction working tables, sale range analysis, price bands, batting order/ranking, buyer group analysis, caller analysis, and quantity/value summaries.

### Important Columns
- `FinYear`
- `Season`
- `SaleNo`
- `Centre`
- `Area`
- `Category`
- `EstBlf`
- `LotStatus`
- `TotalWeight`
- `InvoiceWeight`
- `Value`
- `GardenMDM`
- `SellerGroup`
- `MDMGradeGroup`
- `GradeMDM`
- `Subcategory`
- `SubTeaType`
- `InvoiceNo`
- `LotNo`
- `AuctionDate`
- `GPDate`
- `BuyerMDM`
- `TeaType`
- `BrokerCode`
- `MarkID`
- `MDMCaller`
- `MDMSubCaller`
- `Pkgs`
- `NoOfPacks`
- `NetWeight`
- `ReprintNo`
- `MDMSellerGroup`

### Joins
- Joined to `data-warehousing-prod.EasyReports.Parcon-BuyerGroup` on:
  - `SaleTransactionView.BuyerMDM = Parcon-BuyerGroup.Buyer`
  - `SaleTransactionView.Centre = Parcon-BuyerGroup.Centre`
- Joined to `data-warehousing-prod.EasyReports.Parcon-Caller` on:
  - `SaleTransactionView.MarkID = Parcon-Caller.MarkID`
  - `SaleTransactionView.Centre = Parcon-Caller.Centre`
- Joined to generated price-band CTEs on average price ranges.
- Joined to internally aggregated CTEs on combinations including `FYear`, `GardenMDM`, `Area`, and `EstBlf`.

### Frequently Used Filters
- `Season IN (...)`
- `Season BETWEEN ... AND ...`
- `Season >= EXTRACT(YEAR FROM CURRENT_DATE()) - 3`
- `Season BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 1 AND EXTRACT(YEAR FROM CURRENT_DATE())`
- `Category IN ("CTC", "ORTHODOX")`
- `Category = "CTC"`
- `EstBlf IN ("EST", "BLF")`
- `EstBlf IN ("EST")`
- `Area IN ("AS", "DO", "TR", "CA", "TP")`
- `Centre IN ("KOL", "GUW", "SIL")`
- `Centre NOT IN ("JAL")`
- `BrokerCode IN ("PC")`
- `LotStatus IN ("Sold")`
- Sale range using adjusted sale number:
  - `IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) BETWEEN ... AND ...`
  - `IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) BETWEEN ... AND ...`
- Exclusion pattern:
  - Exclude `Centre = "KOL"` with adjusted sale `55` when `Season <= 2025`
- `MDMSellerGroup LIKE "%MJB-%"`
- `InvoiceNo LIKE "EX%"`

### Common Calculations
- Financial year validation:
  ```sql
  CASE WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear
  ```
- Sale alias:
  ```sql
  IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) AS SaleAlies
  ```
  ```sql
  IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) AS SaleAlies
  ```
- Area alias:
  ```sql
  CASE
    WHEN Area IN ("AS") AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP"
    ELSE ""
  END AS AreaAlies
  ```
- Offer quantity:
  ```sql
  COALESCE(SUM(IF(LotStatus = "Sold", TotalWeight, InvoiceWeight)), 0) AS Offer_Qty
  ```
- Sold quantity:
  ```sql
  SUM(TotalWeight) AS Sold_Qty
  ```
- Total value:
  ```sql
  COALESCE(SUM(Value), 0) AS Total_Value
  ```
- Average price:
  ```sql
  ROUND(SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)), 2) AS AvgPrice
  ```
- Batting order/rank:
  ```sql
  DENSE_RANK() OVER (PARTITION BY ... ORDER BY SUM(Value) / SUM(TotalWeight) DESC)
  ```
- Auction month:
  ```sql
  FORMAT_DATETIME("%B", PARSE_DATE("%d/%m/%Y", AuctionDate)) AS AuctionMonth
  ```
- Auction quarter from `AuctionDate`.
- GP month from `GPDate`.
- Date difference between `AuctionDate` and `GPDate`.
- Lot count:
  ```sql
  COUNT(DISTINCT CONCAT(Season, "-", SaleNo, "-", InvoiceNo, "-", LotNo)) AS TotalLots
  ```
- Price range classification using generated or user-defined bands.
- Buyer group override logic using `BuyerMDM`, `SaleNo`, `Season`, `Centre`, and `TeaType`.

### Example Usage
```sql
SELECT
  CASE WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,
  IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) AS SaleAlies,
  GardenMDM,
  SUM(TotalWeight) AS Sold_Qty,
  COALESCE(SUM(Value), 0) AS Total_Value,
  ROUND(SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)), 2) AS AvgPrice
FROM `data-warehousing-prod.EasyReports.SaleTransactionView`
WHERE Season IN (2023, 2024)
  AND Category = "CTC"
  AND EstBlf IN ("EST")
GROUP BY FYear, SaleAlies, GardenMDM
HAVING FYear <> 0;
```

## `data-warehousing-prod.EasyReports.TeaMart`

### Purpose
TeaMart reporting source used with auction data for combined auction/TeaMart analysis, offer quantity, sold quantity, value, average price, and ranking.

### Important Columns
- `FinYear`
- `Season`
- `WeekNo`
- `GPDATE`
- `EstBlf`
- `Area`
- `Centre`
- `Category`
- `GardenMDM`
- `SellerGroup`
- `Status`
- `TotalWeight`
- `TotalValue`

### Joins
- Combined with aggregated `SaleTransactionView` output using `UNION ALL`.
- No direct table-to-table join is shown in the source SQL.

### Frequently Used Filters
- `Season = 2024`
- `Category IN ("ORTHODOX")`
- `EstBlf IN ("EST")`
- `Centre IN ("KOL", "GUW")`
- `Area IN ("AS")`
- Week range using adjusted week number:
  ```sql
  IF(WeekNo >= 1 AND WeekNo <= 13, 52 + WeekNo, WeekNo) BETWEEN 14 AND 52
  ```
- `HAVING SUM(IF(Status = "Sold", TotalWeight, 0)) > 0`
- `HAVING FYear <> 0`

### Common Calculations
- Financial year validation:
  ```sql
  CASE
    WHEN FinYear IS NOT NULL
      AND LENGTH(FinYear) >= 4
      AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season
    THEN Season ELSE 0
  END AS FYear
  ```
- Area alias.
- Offer quantity:
  ```sql
  SUM(TotalWeight) AS Offer_Qty
  ```
- Sold quantity:
  ```sql
  COALESCE(SUM(IF(Status = "Sold", TotalWeight, 0)), 0) AS Sold_Qty
  ```
- Total value:
  ```sql
  COALESCE(SUM(TotalValue), 0) AS Total_Value
  ```
- Average price:
  ```sql
  ROUND(SAFE_DIVIDE(SUM(TotalValue), SUM(IF(Status = "Sold", TotalWeight, 0))), 2) AS AvgPrice
  ```
- Flush/range classification from `GPDATE`.
- Ranking using `DENSE_RANK()` by average value.

### Example Usage
```sql
SELECT
  CASE
    WHEN FinYear IS NOT NULL
      AND LENGTH(FinYear) >= 4
      AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season
    THEN Season ELSE 0
  END AS FYear,
  GardenMDM,
  SellerGroup,
  SUM(TotalWeight) AS Offer_Qty,
  COALESCE(SUM(IF(Status = "Sold", TotalWeight, 0)), 0) AS Sold_Qty,
  COALESCE(SUM(TotalValue), 0) AS Total_Value
FROM `data-warehousing-prod.EasyReports.TeaMart`
WHERE Season = 2024
  AND Category IN ("ORTHODOX")
  AND EstBlf IN ("EST")
GROUP BY Season, FYear, GardenMDM, SellerGroup
HAVING Sold_Qty > 0 AND FYear <> 0;
```

## `data-warehousing-prod.EasyReports.TI`

### Purpose
TeaInnTech working table source for offer quantity, packages, garden, seller group, and broker/mode labeling.

### Important Columns
- `Season`
- `SaleNo`
- `GardenMDM`
- `SellerGroup`
- `Pkgs`
- `OfferQty`

### Joins
Unknown.

### Frequently Used Filters
- `Season IN (2024, 2025)`
- Adjusted sale number:
  ```sql
  IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) BETWEEN 14 AND 26
  ```

### Common Calculations
- `Season AS FYear`
- Constant values:
  - `"Kol" AS Centre`
  - `"ORTHODOX" AS Category`
  - `"TeaInnTech" AS BrokerCode`
  - `"TeaInnTech" AS Mode`
- `SUM(Pkgs) AS Pkgs`
- `SUM(OfferQty) AS InvoiceWeight`

### Example Usage
```sql
SELECT
  Season AS FYear,
  "Kol" AS Centre,
  "ORTHODOX" AS Category,
  GardenMDM,
  SellerGroup,
  "TeaInnTech" AS BrokerCode,
  SUM(Pkgs) AS Pkgs,
  SUM(OfferQty) AS InvoiceWeight,
  "TeaInnTech" AS Mode
FROM `data-warehousing-prod.EasyReports.TI`
WHERE Season IN (2024, 2025)
  AND IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) BETWEEN 14 AND 26
GROUP BY FYear, Centre, Category, GardenMDM, SellerGroup, BrokerCode, Mode;
```

## `data-warehousing-prod.EasyReports.Parcon-BuyerGroup`

### Purpose
Buyer group lookup used to map buyer names to buyer groups by centre.

### Important Columns
- `Centre`
- `BuyerID`
- `Buyer`
- `BuyerGroup`

### Joins
- Left joined from `SaleTransactionView` buyer analysis on:
  - `SaleTransactionView.BuyerMDM = Parcon-BuyerGroup.Buyer`
  - `SaleTransactionView.Centre = Parcon-BuyerGroup.Centre`

### Frequently Used Filters
- `Centre IN ("KOL", "SIL")`

### Common Calculations
- Buyer group fallback:
  ```sql
  CASE
    WHEN BuyerGroup IS NULL OR BuyerGroup = "" THEN BuyerMDM
    ELSE BuyerGroup
  END AS BuyerGroup
  ```

### Example Usage
```sql
SELECT Centre, BuyerID, Buyer, BuyerGroup
FROM `data-warehousing-prod.EasyReports.Parcon-BuyerGroup`
WHERE Centre IN ("KOL", "SIL");
```

## `data-warehousing-prod.EasyReports.TC_Tasting`

### Purpose
Tasting data source used for tasting working tables and weighted tasting-point calculations.

### Important Columns
- `Location`
- `Tasting_Type`
- `Mark`
- `Invoice`
- `Grade`
- `Category`
- `Sub_Category`
- `Tea_Type`
- `Sub_Tea_Type`
- `Mfg_Date`
- `GP_Date`
- `Tasting_Values`
- `Total_Tasting_Points`
- `Comments`
- `Lot_No`
- `Qty`
- `Season`
- `Sold_Sale_No`
- `Sold_Price`

### Joins
Unknown.

### Frequently Used Filters
- `Season IN (2025)`
- `Tasting_Type IN ("Muster Tasting", "Auction Tasting")`

### Common Calculations
- Split comma-separated `Tasting_Values` into:
  - `Leaf`
  - `Infusion`
  - `Liquor`
- Weighted values:
  - `SUM(Qty) * SUM(Leaf) AS WLeaf`
  - `SUM(Qty) * SUM(Infusion) AS WInfusion`
  - `SUM(Qty) * SUM(Liquor) AS WLiquor`
  - `SUM(Qty) * SUM(Total_Tasting_Points) AS WOverall`

### Example Usage
```sql
SELECT
  Location,
  Tasting_Type,
  Mark,
  Invoice,
  Grade,
  Season,
  SUM(Qty) AS Qty,
  SUM(Total_Tasting_Points) AS Total_Tasting_Points
FROM `data-warehousing-prod.EasyReports.TC_Tasting`
WHERE Season IN (2025)
  AND Tasting_Type IN ("Muster Tasting", "Auction Tasting")
GROUP BY Location, Tasting_Type, Mark, Invoice, Grade, Season;
```

## `data-warehousing-prod.EasyReports.Parcon-Caller`

### Purpose
Caller lookup or budget table used with auction sale transactions to attach budgeted quantity by mark and centre.

### Important Columns
- `MarkID`
- `Centre`
- `BudgetedQty`

### Joins
- Left joined from `SaleTransactionView` caller analysis on:
  - `SaleTransactionView.MarkID = Parcon-Caller.MarkID`
  - `SaleTransactionView.Centre = Parcon-Caller.Centre`

### Frequently Used Filters
Unknown.

### Common Calculations
- `SUM(BudgetedQty) AS BudgetedQty`

### Example Usage
```sql
SELECT *
FROM `data-warehousing-prod.EasyReports.Parcon-Caller`;
```

## `data-warehousing-prod.EasyReports.TC_Privatesale`

### Purpose
Private sale working table source.

### Important Columns
Unknown.

### Joins
Unknown.

### Frequently Used Filters
Unknown.

### Common Calculations
Unknown.

### Example Usage
```sql
SELECT *
FROM `data-warehousing-prod.EasyReports.TC_Privatesale`;
```

## `data-warehousing-prod.EasyReports.CropBGSG`

### Purpose
CropBGSG working table source.

### Important Columns
Unknown.

### Joins
Unknown.

### Frequently Used Filters
Unknown.

### Common Calculations
Unknown.

### Example Usage
```sql
SELECT *
FROM `data-warehousing-prod.EasyReports.CropBGSG`;
```

## `data-warehousing-prod.EasyReports.CropCategoryTB`

### Purpose
CropCategoryTB working table source.

### Important Columns
Unknown.

### Joins
Unknown.

### Frequently Used Filters
Unknown.

### Common Calculations
Unknown.

### Example Usage
```sql
SELECT *
FROM `data-warehousing-prod.EasyReports.CropCategoryTB`;
```

## `data-warehousing-prod.BI_Views.Parcon-Mark`

### Purpose
Unknown.

### Important Columns
Unknown.

### Joins
Unknown.

### Frequently Used Filters
Unknown.

### Common Calculations
Unknown.

### Example Usage
The analyzed SQL only queries metadata for this object:

```sql
SELECT column_name, data_type
FROM `data-warehousing-prod.BI_Views.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = "Parcon-Mark";
```

## `data-warehousing-prod.BI_Views.INFORMATION_SCHEMA.COLUMNS`

### Purpose
Metadata view used to inspect column names and data types in `BI_Views`.

### Important Columns
- `column_name`
- `data_type`
- `table_name`

### Joins
Unknown.

### Frequently Used Filters
- `table_name = "Parcon-Mark"`

### Common Calculations
Unknown.

### Example Usage
```sql
SELECT column_name, data_type
FROM `data-warehousing-prod.BI_Views.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = "Parcon-Mark";
```

## `data-warehousing-prod.EasyReports.INFORMATION_SCHEMA.COLUMNS`

### Purpose
Metadata view used to inspect column names and data types in `EasyReports`.

### Important Columns
- `column_name`
- `data_type`
- `table_name`

### Joins
Unknown.

### Frequently Used Filters
- `table_name = "TeaMart"`
- `table_name = "SaleTransactionView"`

### Common Calculations
Unknown.

### Example Usage
```sql
SELECT column_name, data_type
FROM `data-warehousing-prod.EasyReports.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = "SaleTransactionView";
```
