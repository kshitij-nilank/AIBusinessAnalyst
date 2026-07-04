-- REQ-001
-- Garden-wise Sold Qty, Total Value, and Avg Price for AS CTC EST
-- Sale range: 14 to 26
-- Season comparison: 2026 vs 2025
-- Centre scope: KOL and GUW combined

WITH base AS (
    SELECT
        CASE
            WHEN CAST(SUBSTR(FinYear, 1, 4) AS INT64) = Season THEN Season
            ELSE 0
        END AS FYear,
        IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) AS SaleAlies,
        GardenMDM,
        COALESCE(SUM(TotalWeight), 0) AS Sold_Qty,
        COALESCE(SUM(Value), 0) AS Total_Value
    FROM `data-warehousing-prod.EasyReports.SaleTransactionView`
    WHERE Season IN (2025, 2026)
      AND Area = "AS"
      AND Centre IN ("KOL", "GUW")
      AND Category = "CTC"
      AND EstBlf = "EST"
      AND IF(SaleNo >= 1 AND SaleNo <= 13, 53 + SaleNo, SaleNo) BETWEEN 14 AND 26
    GROUP BY
        FYear,
        SaleAlies,
        GardenMDM
    HAVING FYear <> 0
),
garden_season AS (
    SELECT
        FYear,
        GardenMDM,
        SUM(Sold_Qty) AS Sold_Qty,
        SUM(Total_Value) AS Total_Value,
        ROUND(SAFE_DIVIDE(SUM(Total_Value), SUM(Sold_Qty)), 2) AS Avg_Price
    FROM base
    GROUP BY
        FYear,
        GardenMDM
)
SELECT
    GardenMDM,
    ROUND(SUM(CASE WHEN FYear = 2026 THEN Sold_Qty ELSE 0 END), 2) AS Sold_Qty_2026,
    ROUND(SUM(CASE WHEN FYear = 2026 THEN Total_Value ELSE 0 END), 2) AS Total_Value_2026,
    ROUND(MAX(CASE WHEN FYear = 2026 THEN Avg_Price END), 2) AS Avg_Price_2026,
    ROUND(SUM(CASE WHEN FYear = 2025 THEN Sold_Qty ELSE 0 END), 2) AS Sold_Qty_2025,
    ROUND(SUM(CASE WHEN FYear = 2025 THEN Total_Value ELSE 0 END), 2) AS Total_Value_2025,
    ROUND(MAX(CASE WHEN FYear = 2025 THEN Avg_Price END), 2) AS Avg_Price_2025,
    ROUND(
        SUM(CASE WHEN FYear = 2026 THEN Sold_Qty ELSE 0 END)
        - SUM(CASE WHEN FYear = 2025 THEN Sold_Qty ELSE 0 END),
        2
    ) AS Sold_Qty_Var,
    ROUND(
        SUM(CASE WHEN FYear = 2026 THEN Total_Value ELSE 0 END)
        - SUM(CASE WHEN FYear = 2025 THEN Total_Value ELSE 0 END),
        2
    ) AS Total_Value_Var,
    ROUND(
        COALESCE(MAX(CASE WHEN FYear = 2026 THEN Avg_Price END), 0)
        - COALESCE(MAX(CASE WHEN FYear = 2025 THEN Avg_Price END), 0),
        2
    ) AS Avg_Price_Var
FROM garden_season
GROUP BY GardenMDM
ORDER BY GardenMDM;
