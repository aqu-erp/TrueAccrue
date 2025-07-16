import streamlit as st
import pandas as pd
from io import BytesIO

def load_data():
    """Load data from uploaded files"""
    raw_data = None
    report_format = None
    
    # File uploaders
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload Raw Data")
        raw_file = st.file_uploader("Choose Raw.csv file", type=['csv'])
        
    with col2:
        st.subheader("Upload Report Format")
        report_file = st.file_uploader("Choose Report format file", type=['csv', 'xlsx'])
    
    if raw_file is not None:
        raw_data = pd.read_csv(raw_file)
        st.success(f"Raw data loaded: {len(raw_data)} rows, {len(raw_data.columns)} columns")
    
    if report_file is not None:
        try:
            # Handle both CSV and Excel files
            if report_file.name.endswith('.csv'):
                report_format = {'Sheet1': pd.read_csv(report_file)}
                st.success("Report format loaded from CSV")
            else:
                # Try reading Excel with pandas default engine
                try:
                    report_format = pd.read_excel(report_file, sheet_name=None)
                    st.success(f"Report format loaded: {len(report_format)} sheets")
                except Exception as excel_error:
                    st.error(f"Excel read failed: {excel_error}")
                    st.info("Please convert your Excel file to CSV format and re-upload")
                    report_format = None
        except Exception as e:
            st.error(f"Error reading file: {e}")
    
    return raw_data, report_format

def create_summary_report(df):
    """Create time series report grouped by vendor then account with anomaly detection"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Clean amount column
    if 'Amount' in df.columns:
        df['Amount_Numeric'] = pd.to_numeric(df['Amount'].astype(str).str.replace(',', ''), errors='coerce')
    else:
        df['Amount_Numeric'] = 0
    
    # Determine period column
    period_col = None
    if 'Accounting Period: Name' in df.columns:
        period_col = 'Accounting Period: Name'
    elif 'Accounting Period' in df.columns:
        period_col = 'Accounting Period'
    
    # Check required columns
    if not all(col in df.columns for col in ['Vendor', 'Account']) or period_col is None:
        return pd.DataFrame()
    
    # Create pivot table: Vendor+Account as rows, Periods as columns
    pivot_df = df.pivot_table(
        index=['Vendor', 'Account'],
        columns=period_col,
        values='Amount_Numeric',
        aggfunc='sum',
        fill_value=0
    ).round(2)
    
    # Reset index to make Vendor and Account regular columns
    pivot_df = pivot_df.reset_index()
    
    # Get period columns (sorted to identify latest)
    period_cols = [col for col in pivot_df.columns if col not in ['Vendor', 'Account']]
    period_cols_sorted = sorted(period_cols)
    
    if len(period_cols_sorted) >= 2:
        latest_period = period_cols_sorted[-1]
        historical_periods = period_cols_sorted[:-1]
        
        # Calculate historical average (excluding zeros)
        pivot_df['Historical_Avg'] = pivot_df[historical_periods].replace(0, pd.NA).mean(axis=1, skipna=True).fillna(0)
        
        # Anomaly detection flags
        pivot_df['Latest_Amount'] = pivot_df[latest_period]
        
        # Flag potential issues using numpy.select
        import numpy as np
        
        conditions = [
            # Missing/zero in latest but had historical activity
            (pivot_df['Latest_Amount'] == 0) & (pivot_df['Historical_Avg'] > 0),
            # Significant decrease (>50% below historical average)
            (pivot_df['Latest_Amount'] > 0) & (pivot_df['Historical_Avg'] > 0) & 
            (pivot_df['Latest_Amount'] < pivot_df['Historical_Avg'] * 0.5)
        ]
        
        choices = ['🚨 Missing', '⚠️ Low', '✅ Normal']
        pivot_df['Alert'] = np.select(conditions, choices[:-1], default=choices[-1])
        
        # Calculate variance from historical
        pivot_df['Variance_%'] = ((pivot_df['Latest_Amount'] - pivot_df['Historical_Avg']) / 
                                 pivot_df['Historical_Avg'] * 100).round(1)
        pivot_df['Variance_%'] = pivot_df['Variance_%'].fillna(0)
    
    # Add total column
    pivot_df['Total'] = pivot_df[period_cols].sum(axis=1)
    
    return pivot_df

def create_detailed_report(df):
    """Create a detailed report maintaining original format"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Select key columns for detailed view
    detail_cols = ['Account', 'Name', 'Description', 'Amount', 'Accounting Period: Name', 'Vendor']
    available_cols = [col for col in detail_cols if col in df.columns]
    
    if available_cols:
        detailed = df[available_cols].copy()
        
        # Clean and format amount
        if 'Amount' in detailed.columns:
            detailed['Amount_Clean'] = pd.to_numeric(
                detailed['Amount'].astype(str).str.replace(',', ''), 
                errors='coerce'
            )
            detailed['Amount_Formatted'] = detailed['Amount_Clean'].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00"
            )
        
        return detailed
    else:
        return df

def main():
    st.title("Journal Entry Report Generator")
    st.markdown("Upload your Raw.csv and Report.xlsx files to generate the formatted report")
    
    # Load data
    raw_data, report_format = load_data()
    
    if raw_data is not None:
        st.header("Raw Data Preview")
        st.dataframe(raw_data.head(10))
        
        # Show data info
        st.subheader("Data Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", len(raw_data))
        with col2:
            st.metric("Total Columns", len(raw_data.columns))
        with col3:
            if 'Amount' in raw_data.columns:
                total_amount = pd.to_numeric(
                    raw_data['Amount'].astype(str).str.replace(',', ''), 
                    errors='coerce'
                ).sum()
                st.metric("Total Amount", f"${total_amount:,.2f}")
        
        # Generate reports
        st.header("Generated Reports")
        
        tab1, tab2 = st.tabs(["Time Series Report", "Detailed Report"])
        
        with tab1:
            st.subheader("Time Series by Vendor and Account")
            summary_df = create_summary_report(raw_data)
            if not summary_df.empty:
                # Alert filtering
                if 'Alert' in summary_df.columns:
                    alert_filter = st.selectbox(
                        "Filter by Alert Type:",
                        ['All', '🚨 Missing', '⚠️ Low', '✅ Normal']
                    )
                    
                    if alert_filter != 'All':
                        filtered_df = summary_df[summary_df['Alert'] == alert_filter]
                    else:
                        filtered_df = summary_df
                    
                    # Show alert summary
                    if 'Alert' in summary_df.columns:
                        alert_counts = summary_df['Alert'].value_counts()
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🚨 Missing", alert_counts.get('🚨 Missing', 0))
                        with col2:
                            st.metric("⚠️ Low", alert_counts.get('⚠️ Low', 0))
                        with col3:
                            st.metric("✅ Normal", alert_counts.get('✅ Normal', 0))
                else:
                    filtered_df = summary_df
                
                # Style the dataframe to highlight alerts
                def highlight_alerts(row):
                    if 'Alert' in row.index:
                        if row['Alert'] == '🚨 Missing':
                            return ['background-color: #ffebee'] * len(row)
                        elif row['Alert'] == '⚠️ Low':
                            return ['background-color: #fff3e0'] * len(row)
                    return [''] * len(row)
                
                styled_df = filtered_df.style.apply(highlight_alerts, axis=1)
                st.dataframe(styled_df, use_container_width=True)
                
                st.info(f"Report shows {len(filtered_df)} vendor-account combinations. Red=Missing expenses, Orange=Low expenses")
                
                # Download option
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download Time Series Report as CSV",
                    data=csv,
                    file_name="time_series_report.csv",
                    mime="text/csv"
                )
            else:
                st.error("Unable to create time series report. Check that Vendor, Account, and Accounting Period columns exist.")
        
        with tab2:
            st.subheader("Detailed Transaction Report")
            detailed_df = create_detailed_report(raw_data)
            if not detailed_df.empty:
                st.dataframe(detailed_df, use_container_width=True)
                
                # Download option
                csv = detailed_df.to_csv(index=False)
                st.download_button(
                    label="Download Details as CSV",
                    data=csv,
                    file_name="detailed_report.csv",
                    mime="text/csv"
                )
            else:
                st.info("Unable to create detailed report")
    
    if report_format is not None:
        st.header("Report Format Reference")
        for sheet_name, sheet_data in report_format.items():
            with st.expander(f"Sheet: {sheet_name}"):
                st.dataframe(sheet_data)

if __name__ == "__main__":
    main()
