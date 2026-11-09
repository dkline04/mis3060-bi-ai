# Model metadata – hw06.pbix

Exported from **DAX query view** in `hw06.pbix` (started from the posted `Wildcat_Star_Model.pbix`) on Nov 8, 2026, using the three INFO.VIEW queries in `powerbi_dax_guide.md` §2. I exported it **after** adding measures 0–10 and **before** writing measure 11 (`Top 10 Client Share`), which is the Part D measure. So Claude saw the measures it could reuse (`[Ending AUM]` and the others) but not the answer. Format strings are blank because formatting was applied afterwards.

The `DateTableTemplate_…` and `LocalDateTable_…` tables are hidden tables that Power BI's Auto date/time setting creates in the posted model. None of the measures use them.

## What the metadata does NOT say (added to the prompt by hand)
- **Grain of `fact_portfolio_snapshot`:** one row per client per month. `snapshot_date` is always the **1st** of the month. Dec 1, 2024 is the latest snapshot.
- **`aum` is a balance** (semi-additive). Never sum it across months; read it at the last snapshot in the filter.
- **`active_alpha_ytd` is a year-to-date rate.** Read it at the last snapshot only, weight it by `aum`, and exclude `is_return_suspect = 1`.
- `dim_date` is marked as the date table and joined on `dim_date[date]`.
- 175 of the 2,500 clients have left. Their last snapshot is before Dec 2024.

---

## 1. Columns

```DAX
EVALUATE
SELECTCOLUMNS (
    FILTER ( INFO.VIEW.COLUMNS (), [DataCategory] <> "RowNumber" ),
    [Table], "Column", [Name], [DataType], "DAX formula", [Expression], [IsHidden]
)
ORDER BY [Table]
```

| Table | Column | DataType | DAX formula | IsHidden |
|---|---|---|---|---|
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Date | Date |  | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Day | Integer | DAY([Date]) | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Quarter | Text | "Qtr " & [QuarterNo] | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Month | Text | FORMAT([Date], "MMMM") | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | MonthNo | Integer | MONTH([Date]) | true |
| DateTableTemplate_b50879b8-a09d-4fd7-b9a6-7a34995295aa | Year | Integer | YEAR([Date]) | true |
| dim_advisor | years_experience | Integer |  | false |
| dim_advisor | certifications | Text |  | false |
| dim_advisor | advisor_id | Integer |  | false |
| dim_advisor | first_name | Text |  | false |
| dim_advisor | last_name | Text |  | false |
| dim_advisor | region | Text |  | false |
| dim_advisor | aum_target_mm | Integer |  | false |
| dim_benchmark | ticker_proxy | Text |  | false |
| dim_benchmark | asset_class | Text |  | false |
| dim_benchmark | name | Text |  | false |
| dim_benchmark | benchmark_id | Integer |  | false |
| dim_client | client_since | Date |  | false |
| dim_client | first_name | Text |  | false |
| dim_client | primary_account_type | Text |  | false |
| dim_client | client_tier | Text |  | false |
| dim_client | risk_profile | Text |  | false |
| dim_client | zip_code | Text |  | false |
| dim_client | state | Text |  | false |
| dim_client | city | Text |  | false |
| dim_client | age | Integer |  | false |
| dim_client | last_name | Text |  | false |
| dim_client | initial_aum | Number |  | false |
| dim_client | client_id | Integer |  | false |
| dim_client | is_active | True/False |  | false |
| dim_client | advisor_id | Integer |  | false |
| dim_date | is_quarter_end | Integer |  | false |
| dim_date | is_year_end | Integer |  | false |
| dim_date | is_trading_day | Integer |  | false |
| dim_date | Year | Integer |  | false |
| dim_date | Date | Date |  | false |
| dim_date | date_id | Integer |  | false |
| dim_date | Month | Integer |  | false |
| dim_date | Quarter | Integer |  | false |
| dim_date | month_name | Text |  | false |
| dim_date | week_of_year | Integer |  | false |
| dim_date | day_of_week | Text |  | false |
| dim_date | is_month_end | Integer |  | false |
| dim_security | expense_ratio_bps | Integer |  | false |
| dim_security | security_id | Integer |  | false |
| dim_security | ticker | Text |  | false |
| dim_security | name | Text |  | false |
| dim_security | asset_class | Text |  | false |
| dim_security | sector | Text |  | false |
| dim_security | benchmark_id | Integer |  | false |
| dim_security | is_etf | True/False |  | false |
| fact_fees | fee_date | Date |  | false |
| fact_fees | fee_type | Text |  | false |
| fact_fees | aum_basis | Number |  | false |
| fact_fees | bps_charged | Number |  | false |
| fact_fees | amount | Number |  | false |
| fact_fees | fee_id | Integer |  | false |
| fact_fees | client_id | Integer |  | false |
| fact_fees | advisor_id | Integer |  | false |
| fact_portfolio_snapshot | Year | Integer |  | false |
| fact_portfolio_snapshot | snapshot_date | Date |  | false |
| fact_portfolio_snapshot | benchmark_id | Integer |  | false |
| fact_portfolio_snapshot | advisor_id | Integer |  | false |
| fact_portfolio_snapshot | client_id | Integer |  | false |
| fact_portfolio_snapshot | snapshot_id | Integer |  | false |
| fact_portfolio_snapshot | benchmark_return_ytd | Number |  | false |
| fact_portfolio_snapshot | is_return_suspect | Integer |  | false |
| fact_portfolio_snapshot | account_type | Text |  | false |
| fact_portfolio_snapshot | cash_pct | Number |  | false |
| fact_portfolio_snapshot | active_alpha_ytd | Number |  | false |
| fact_portfolio_snapshot | return_ytd | Number |  | false |
| fact_portfolio_snapshot | aum | Number |  | false |
| fact_portfolio_snapshot | Month | Integer |  | false |
| fact_transactions | security_id | Integer |  | false |
| fact_transactions | shares | Number |  | false |
| fact_transactions | is_post_departure_txn | Integer |  | false |
| fact_transactions | txn_type | Text |  | false |
| fact_transactions | txn_date | Date |  | false |
| fact_transactions | price | Number |  | false |
| fact_transactions | txn_id | Integer |  | false |
| fact_transactions | advisor_id | Integer |  | false |
| fact_transactions | client_id | Integer |  | false |
| fact_transactions | amount | Number |  | false |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Month | Text | FORMAT([Date], "MMMM") | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Date | Date |  | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Year | Integer | YEAR([Date]) | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | MonthNo | Integer | MONTH([Date]) | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Quarter | Text | "Qtr " & [QuarterNo] | true |
| LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | Day | Integer | DAY([Date]) | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Day | Integer | DAY([Date]) | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Quarter | Text | "Qtr " & [QuarterNo] | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | QuarterNo | Integer | INT(([MonthNo] + 2) / 3) | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Month | Text | FORMAT([Date], "MMMM") | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | MonthNo | Integer | MONTH([Date]) | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Year | Integer | YEAR([Date]) | true |
| LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | Date | Date |  | true |

## 2. Relationships

```DAX
EVALUATE INFO.VIEW.RELATIONSHIPS ()
```

(The ID, Name and Model columns are internal IDs and are left out to keep the table readable. The first 11 rows are the star schema. The last three are the snowflake link and the two hidden Auto date/time links.)

| Relationship | IsActive | CrossFilteringBehavior | FromTable | FromColumn | FromCardinality | ToTable | ToColumn | ToCardinality | State |
|---|---|---|---|---|---|---|---|---|---|
| 'fact_transactions'[advisor_id] *[<-]1 'dim_advisor'[advisor_id] | true | OneDirection | fact_transactions | advisor_id | Many | dim_advisor | advisor_id | One | Ready |
| 'fact_transactions'[client_id] *[<-]1 'dim_client'[client_id] | true | OneDirection | fact_transactions | client_id | Many | dim_client | client_id | One | Ready |
| 'fact_transactions'[security_id] *[<-]1 'dim_security'[security_id] | true | OneDirection | fact_transactions | security_id | Many | dim_security | security_id | One | Ready |
| 'fact_transactions'[txn_date] *[<-]1 'dim_date'[date] | true | OneDirection | fact_transactions | txn_date | Many | dim_date | date | One | Ready |
| 'fact_portfolio_snapshot'[advisor_id] *[<-]1 'dim_advisor'[advisor_id] | true | OneDirection | fact_portfolio_snapshot | advisor_id | Many | dim_advisor | advisor_id | One | Ready |
| 'fact_portfolio_snapshot'[benchmark_id] *[<-]1 'dim_benchmark'[benchmark_id] | true | OneDirection | fact_portfolio_snapshot | benchmark_id | Many | dim_benchmark | benchmark_id | One | Ready |
| 'fact_portfolio_snapshot'[client_id] *[<-]1 'dim_client'[client_id] | true | OneDirection | fact_portfolio_snapshot | client_id | Many | dim_client | client_id | One | Ready |
| 'fact_portfolio_snapshot'[snapshot_date] *[<-]1 'dim_date'[date] | true | OneDirection | fact_portfolio_snapshot | snapshot_date | Many | dim_date | date | One | Ready |
| 'fact_fees'[advisor_id] *[<-]1 'dim_advisor'[advisor_id] | true | OneDirection | fact_fees | advisor_id | Many | dim_advisor | advisor_id | One | Ready |
| 'fact_fees'[client_id] *[<-]1 'dim_client'[client_id] | true | OneDirection | fact_fees | client_id | Many | dim_client | client_id | One | Ready |
| 'fact_fees'[fee_date] *[<-]1 'dim_date'[date] | true | OneDirection | fact_fees | fee_date | Many | dim_date | date | One | Ready |
| 'dim_client'[client_since] *[<-]1 'LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8'[Date] | true | OneDirection | dim_client | client_since | Many | LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8 | date | One | Ready |
| 'dim_date'[date] *[<-]1 'LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7'[Date] | true | OneDirection | dim_date | date | Many | LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7 | date | One | Ready |
| 'dim_security'[benchmark_id] *[<-]1 'dim_benchmark'[benchmark_id] | true | OneDirection | dim_security | benchmark_id | Many | dim_benchmark | benchmark_id | One | Ready |

## 3. Measures

```DAX
EVALUATE
SELECTCOLUMNS (
    INFO.VIEW.MEASURES (),
    [Table], "Measure", [Name], "DAX formula", [Expression], [FormatString], [State]
)
```

| Table | Measure | DAX formula | FormatString | State |
|---|---|---|---|---|
| _Measures | Total Fees | SUM ( fact_fees[amount] ) |  | Valid |
| _Measures | Net Flows | CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" ) - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" ) |  | Valid |
| _Measures | AUM (naive SUM) | SUM ( fact_portfolio_snapshot[aum] ) |  | Valid |
| _Measures | Ending AUM | CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) ) |  | Valid |
| _Measures | Ending Clients | CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) ) |  | Valid |
| _Measures | Avg AUM per Client | DIVIDE ( [Ending AUM], [Ending Clients] ) |  | Valid |
| _Measures | Ending AUM LY | CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) ) |  | Valid |
| _Measures | AUM YoY % | DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] ) |  | Valid |
| _Measures | Ending AUM PM | CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) ) |  | Valid |
| _Measures | AUM MoM % | DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] ) |  | Valid |
| _Measures | Avg Monthly AUM | DIVIDE ( SUM ( fact_portfolio_snapshot[aum] ), DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] ) ) |  | Valid |
| _Measures | Fee Yield (bps) | DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) ) |  | Valid |
| _Measures | Organic Growth Rate | DIVIDE ( [Net Flows], [Ending AUM LY] ) |  | Valid |
| _Measures | AUM-Weighted Alpha | VAR LastSnap = LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ) RETURN CALCULATE ( DIVIDE ( SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ), SUM ( fact_portfolio_snapshot[aum] ) ), LastSnap, fact_portfolio_snapshot[is_return_suspect] = 0 ) |  | Valid |
| _Measures | Alpha Signal | VAR a = [AUM-Weighted Alpha] RETURN SWITCH ( TRUE (), ISBLANK ( a ), BLANK (), a >= 0.02, "Outperforming", a <= -0.02, "Lagging", "In line" ) |  | Valid |
