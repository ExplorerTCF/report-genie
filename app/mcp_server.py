from mcp.server.fastmcp import FastMCP

mcp = FastMCP("report-genie-db")

@mcp.tool()
def query_database(query: str) -> str:
    """Query the corporate sales and metrics database.
    
    Args:
        query: SQL-like description of what metrics to retrieve (e.g. 'sales by product Q2').
    """
    q = query.lower()
    if "sales" in q or "revenue" in q:
        return (
            "Quarterly Sales & Revenue Data (2026):\n"
            "| Quarter | Product A | Product B | Total Revenue |\n"
            "|---------|-----------|-----------|--------------|\n"
            "| Q1 2026 | $120,000  | $85,000   | $205,000     |\n"
            "| Q2 2026 | $145,000  | $98,000   | $243,000     |\n"
            "| Q3 2026 | $160,000  | $110,000  | $270,000     |\n"
            "| Q4 2026 | $190,000  | $135,000  | $325,000     |\n"
        )
    elif "employee" in q or "hr" in q or "staff" in q:
        return (
            "Department Headcount & Performance Index:\n"
            "- Engineering: 24 members, Index: 92.4\n"
            "- Sales & Marketing: 12 members, Index: 88.1\n"
            "- Customer Support: 15 members, Index: 95.0\n"
            "- Operations: 6 members, Index: 90.5\n"
        )
    else:
        return (
            "Metrics Search Result for '" + query + "':\n"
            "Active Customers: 1,420 (+12% MoM)\n"
            "Churn Rate: 1.8% (-0.4% MoM)\n"
            "NPS Score: 74\n"
        )

@mcp.tool()
def read_business_file(file_name: str) -> str:
    """Read contents of business files/logs from disk.
    
    Args:
        file_name: Name of the business log file to read (e.g. 'q2_support_log.csv').
    """
    fn = file_name.lower()
    if "support" in fn:
        return (
            "Ticket ID,Date,Category,Priority,Status,ResolutionTime(hrs)\n"
            "TK-101,2026-06-01,Billing,High,Resolved,2.5\n"
            "TK-102,2026-06-02,Technical,Medium,Resolved,4.0\n"
            "TK-103,2026-06-03,Account,Low,Resolved,1.2\n"
            "TK-104,2026-06-05,Billing,High,Open,N/A\n"
            "TK-105,2026-06-06,Technical,Critical,Resolved,0.8\n"
        )
    elif "marketing" in fn or "campaign" in fn:
        return (
            "Campaign,Channel,Budget,Spend,Conversions,CAC\n"
            "Summer Spark,Google Ads,$5000,$4820,320,$15.06\n"
            "Social Boost,Meta Ads,$3000,$2950,210,$14.05\n"
            "Newsletter,Email,$500,$480,85,$5.65\n"
        )
    else:
        return f"File '{file_name}' not found. Available mock files are: 'q2_support_log.csv', 'marketing_campaign_data.csv'."

@mcp.tool()
def generate_chart_data(metric_name: str) -> str:
    """Generate visual ASCII charts based on a business metric.
    
    Args:
        metric_name: Name of the metric to plot (e.g., 'sales', 'conversions').
    """
    m = metric_name.lower()
    if "sales" in m or "revenue" in m:
        return (
            "ASCII Sales Trend Chart (2026):\n"
            "Q1: [████████████] $205K\n"
            "Q2: [███████████████] $243K\n"
            "Q3: [█████████████████] $270K\n"
            "Q4: [█████████████████████] $325K\n"
        )
    elif "conversions" in m or "leads" in m:
        return (
            "ASCII Conversions Chart:\n"
            "Google Ads: [████████████████] 320\n"
            "Meta Ads:   [██████████] 210\n"
            "Email:      [████] 85\n"
        )
    else:
        return f"No chart data available for metric '{metric_name}'."

if __name__ == "__main__":
    mcp.run()
