--------------------------------------------------------------
/* AUC - AREA ALIES */
--------------------------------------------------------------

Case 
when Area IN ("AS") and Centre IN("KOL","GUW") then "AS"
when Area IN ("DO","TR") and Centre IN("KOL","SIL") then "DO/TR" 
when Area IN ("CA","TP") and Centre IN("KOL","GUW") then "CA/TP" else "OTHERS" end as AreaAlies


--------------------------------------------------------------
/* AUC - AUCTION DATE TO AuctionMonth */
--------------------------------------------------------------
FORMAT_DATETIME("%B", (PARSE_DATE("%d/%m/%Y", AuctionDate))) As AuctionMonth

--------------------------------------------------------------
/* AUCTION DATE TO QUARTER */
--------------------------------------------------------------
CASE
    WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (4, 5, 6) THEN 'Q1'
    WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (7, 8, 9) THEN 'Q2'
    WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (10, 11, 12) THEN 'Q3'
	WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (1, 2, 3) THEN 'Q4' ELSE ""
END AS AuctionQuarter,


--------------------------------------------------------------
/* AUC - GPDate TO GPMonth */
--------------------------------------------------------------

FORMAT_DATETIME("%B", DATETIME(GPDate)) As GPMonth,

/* If GP_Date is STRING: */
FORMAT_DATE('%B', PARSE_DATE('%Y-%m-%d', SUBSTR(GP_Date, 2))) As GPMonth


--------------------------------------------------------------
EXTRACT(MONTH FROM GPDATE)
--------------------------------------------------------------
 
 ((EXTRACT(MONTH FROM GPDATE) = 10 AND EXTRACT(DAY FROM GPDATE) >= 16)
    OR (EXTRACT(MONTH FROM GPDATE) BETWEEN 11 AND 12)
    OR (EXTRACT(MONTH FROM GPDATE) BETWEEN 1 AND 3 AND EXTRACT(DAY FROM GPDATE) <= 31))
	

--------------------------------------------------------------
GPDATE BETWEEN
--------------------------------------------------------------

DATE(GPDate) BETWEEN PARSE_DATE('%d/%m/%Y','25/06/2024') AND PARSE_DATE('%d/%m/%Y','07/11/2024')

--------------------------------------------------------------
DATE DIFF
--------------------------------------------------------------

CASE 
    WHEN DATE_DIFF(PARSE_DATE("%d/%m/%Y", AuctionDate),DATE(GPDate), DAY) <= 45 and LotStatus IN ("Sold") THEN "Within 45 days from GP Date"
    ELSE "Beyond 45 days from GP Date" 
	END AS `Within_Beyond`,
DATE_DIFF(DATE(GPDate), PARSE_DATE("%d/%m/%Y", AuctionDate), DAY) AS `Days_Difference`,

--------------------------------------------------------------
WORKING WITH ReprintNo
--------------------------------------------------------------
CONCAT("Reprint - ", CAST(ReprintNo AS STRING)) AS Reprint_Status

--------------------------------------------------------------
MAX SALE NO.
--------------------------------------------------------------
if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) between 14 and (Select max(if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo)) from `data-warehousing-prod.EasyReports.SaleTransactionView` where Season = 2025 and FinYear = "2025-26")

--------------------------------------------------------------
PACKAGES
--------------------------------------------------------------
if(LotStatus="Sold",sum(Pkgs),sum(NoOfPacks)) AS Pkgs


--------------------------------------------------------------
NetWeight AND Packs
--------------------------------------------------------------


NoOfPacks,
LotStatus,

if(LotStatus="Sold",Pkgs,NoOfPacks) AS PACKS,

Cast(NetWeight as string) as NetWeight,

--------------------------------------------------------------
FOR UPTO RANGE ALIES - ADD FOR
--------------------------------------------------------------

Case when if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) between 14 and 53 then "UPTO" else "" end as RangeAlies,

--------------------------------------------------------------
MRIL GRADE UNIQENESS
--------------------------------------------------------------

Case when GradeMDM IN ("TGFOP1", "TGFOP", "GFOP", "FOP") and Category IN ("ORTHODOX") then "Whole Leaf"
when GradeMDM IN ("FBOP", "GFBOP", "GBOP", "BOP1","BPS1") and Category IN ("ORTHODOX") then "Brokens"
when GradeMDM IN ("BOPF") and Category IN ("ORTHODOX") then "Fannings"
when GradeMDM IN ("GBOP1", "FBOP1", "OD") and Category IN ("ORTHODOX") then "Secondaries" 
else "" end as GradeAlies,


---------------
Season EXTRACT
---------------
WHERE Season >= EXTRACT(YEAR FROM CURRENT_DATE()) - 3

--------------------------------------------------------------
Convert to String
--------------------------------------------------------------
Cast(if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) as String) as SaleAlies


--------------------------------------------------------------
EXTRACT INVOICE NO
--------------------------------------------------------------

REGEXP_SUBSTR(InvoiceNo, '^[A-Za-z]+') AS InvoicePrefix

REGEXP_SUBSTR(InvoiceNo, '[0-9]+') AS InvoiceNumber


InvoiceNo LIKE "EX%"
	
--------------------------
INFORMATION_SCHEMA_AUCTION
--------------------------
SELECT 
  column_name, 
  data_type
FROM 
  `data-warehousing-prod.BI_Views.INFORMATION_SCHEMA.COLUMNS`
WHERE 
  table_name = 'Parcon-Mark'
  
  
--------------------------
INFORMATION_SCHEMA_TEAMART
--------------------------
  
  
SELECT column_name,data_type

FROM data-warehousing-prod.EasyReports.INFORMATION_SCHEMA.COLUMNS

WHERE table_name = 'TeaMart'

--------------------------------------------------------------
INFORMATION SCHEMA
--------------------------------------------------------------


SELECT 
  column_name, 
  data_type
FROM 
  `data-warehousing-prod.EasyReports.INFORMATION_SCHEMA.COLUMNS`
WHERE 
  table_name = 'SaleTransactionView'
  
  
  
  ------------------------------------------------
DIFFERENT SALE IN DIFFERENT CENTRE CASE HANDLING
------------------------------------------------

  AND NOT (
      Centre = "KOL"
      AND if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) = 55
      AND Season <= 2025
  )
  
------------------------------------------------
TMART BrokerCode
------------------------------------------------
  CASE 
WHEN BrokerCode IN ("SCPL") THEN "PC"
WHEN BrokerCode IN ("TCPS") THEN "JT"
WHEN BrokerCode IN ("Merlin") THEN "CB"
    ELSE "" END AS BrokerCode,
	
	
------------------------------------------------
LIKE
------------------------------------------------	
MDMSellerGroup Like "%MJB-%"

------------------------
auto-rolls every year
------------------------

WHERE Season BETWEEN EXTRACT(YEAR FROM CURRENT_DATE()) - 1
AND EXTRACT(YEAR FROM CURRENT_DATE())


-------------------
/* FLUSH SPECIAL CODE */
-------------------
t2 as(
SELECT *,
CASE 
WHEN SellerGroup = "GOODRICKE" AND Sold_Qty >= 0.001 THEN DENSE_RANK()OVER (PARTITION BY FYear, RangeAlies, EstBlf ORDER BY Total_Value / Sold_Qty DESC)
WHEN SellerGroup <> "GOODRICKE" AND Sold_Qty >= 50000 THEN DENSE_RANK() OVER (PARTITION BY FYear, RangeAlies, EstBlf ORDER BY Total_Value / Sold_Qty DESC)

ELSE 0 END AS ESTBOP 

FROM 

(SELECT * FROM t1
 WHERE (SellerGroup = "GOODRICKE" AND Sold_Qty >= 0.001) OR (SellerGroup <> "GOODRICKE" AND Sold_Qty >= 50000))

 UNION ALL

 SELECT *, 0 AS ESTBOP
 FROM t1
  WHERE NOT((SellerGroup = "GOODRICKE" AND Sold_Qty >= 0.001) OR (SellerGroup <> "GOODRICKE" AND Sold_Qty >= 50000)))
  
 
 
 
 ---------------------------------------------------------------------------------------------------------
/*  PRICE RANGE SPECIAL CODE */
 ---------------------------------------------------------------------------------------------------------
DECLARE min_price FLOAT64 DEFAULT 100;
DECLARE max_price FLOAT64 DEFAULT 400;
DECLARE increment FLOAT64 DEFAULT 20;


-- 1 Base Aggregated Data

WITH base AS (
SELECT
    CASE 
        WHEN CAST(SUBSTR(FinYear,1,4) AS INT64) = Season 
        THEN Season ELSE 0 
    END AS FYear,

    InvoiceNo,
    LotNo,
    IF(SaleNo BETWEEN 1 AND 13, 53+SaleNo, SaleNo) AS SaleAlies,
    EstBlf,

    SUM(TotalWeight) AS Sold_Qty,
    SUM(Value) AS Total_Value,

    SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)) AS AvgPrice

FROM `data-warehousing-prod.EasyReports.SaleTransactionView`

WHERE Centre = "KOL"
AND Category = "CTC"
AND Season IN (2023,2024,2025)

GROUP BY FYear, InvoiceNo, LotNo, SaleAlies, EstBlf
HAVING SUM(TotalWeight) > 0
AND FYear <> 0
),


-- 2 Generate Dynamic Price Bands

bands AS (
SELECT
    band_start,
    band_start + increment AS band_end
FROM UNNEST(
        GENERATE_ARRAY(min_price, max_price - increment, increment)
     ) AS band_start
)


-- 3 Final Join

SELECT
    b.FYear,
    b.SaleAlies,
    b.EstBlf,
    band_start,
    band_end,
    CONCAT(CAST(band_start AS STRING), "-", CAST(band_end AS STRING)) AS PriceRange,
    SUM(b.Sold_Qty) AS Total_Qty,
    ROUND(SUM(b.Total_Value),2) AS Total_Value

FROM base b
JOIN bands
ON b.AvgPrice >= band_start
AND b.AvgPrice < band_end

GROUP BY b.FYear, b.SaleAlies, b.EstBlf, band_start, band_end
ORDER BY band_start



-------------------------------------------------------------------------------------------------------------------
/* SPECICIAL CODE FOR PRICE RANGE WITH USER DEFINED BANDS */
-------------------------------------------------------------------------------------------------------------------
 
WITH lot_base AS (
    SELECT
        GardenMDM,
        CASE WHEN CAST(SUBSTR(FinYear,1,4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,
        GradeMDM,
        InvoiceNo,
        LotNo,
        IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo) AS SaleAlies,
        EstBlf,
        BrokerCode,

        SUM(TotalWeight) AS Sold_Qty,
        SUM(Value) AS Total_Value,
        SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)) AS AvgPrice

    FROM `data-warehousing-prod.EasyReports.SaleTransactionView`

    WHERE Centre = "KOL" AND Category = "CTC" AND Season IN (2023,2024,2025)

    GROUP BY GardenMDM, FYear, InvoiceNo, LotNo, SaleAlies, EstBlf, GradeMDM, BrokerCode

    HAVING SUM(TotalWeight) > 0 AND FYear <> 0
),

-- 🔥 USER DEFINED BANDS (EDIT HERE ONLY)
bands AS (
    SELECT 100 AS band_start, 120 AS band_end, '100-120' AS PriceRange UNION ALL
    SELECT 120, 150, '120-150' UNION ALL
    SELECT 150, 250, '150-250' UNION ALL
    SELECT 250, 400, '250-400'
),

band_limits AS (
    SELECT 
	MIN(band_start) AS min_band,
    MAX(band_end) AS max_band
    FROM bands
),

classified AS (

    -- BELOW MIN
    SELECT l.*, CONCAT('BELOW ', CAST(bl.min_band AS STRING)) AS PriceRange
    FROM lot_base l
    CROSS JOIN band_limits bl
    WHERE l.AvgPrice < bl.min_band

    UNION ALL

    -- CUSTOM BANDS
    SELECT l.*, b.PriceRange
    FROM lot_base l
    JOIN bands b
    ON l.AvgPrice >= b.band_start
    AND l.AvgPrice <  b.band_end

    UNION ALL

    -- ABOVE MAX
    SELECT l.*, CONCAT('ABOVE ', CAST(bl.max_band AS STRING)) AS PriceRange
    FROM lot_base l
    CROSS JOIN band_limits bl
    WHERE l.AvgPrice >= bl.max_band
)

SELECT
    FYear, GardenMDM, SaleAlies, GradeMDM,InvoiceNo,LotNo,EstBlf, BrokerCode,
    SUM(Sold_Qty) AS Sold_Qty,
    ROUND(SUM(Total_Value), 2) AS Total_Value,
    PriceRange

FROM classified

GROUP BY GardenMDM, FYear, SaleAlies, EstBlf, PriceRange, InvoiceNo, LotNo, GradeMDM, BrokerCode

ORDER BY GardenMDM, PriceRange, GradeMDM;

 
--------------------------------------------------------------
/* LOT COUNT */
--------------------------------------------------------------
COUNT(DISTINCT CONCAT(Season,'-',SaleNo,'-',InvoiceNo,'-',LotNo)) AS TotalLots,


--------------------------------------------------------------
/* TM - AUCTION DATE TO AuctionMonth */
--------------------------------------------------------------
FORMAT_DATE('%B', AuctionDate) AS AuctionMonth,




