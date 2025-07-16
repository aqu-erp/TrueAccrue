import streamlit as st
import pandas as pd
import openpyxl
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
        report_file = st.file_uploader("Choose Report.xlsx file", type=['xlsx'])
    
    if raw_file is not None:
        raw_data = pd.read_csv(raw_file)
        st.success(f"Raw data loaded: {len(raw_data)} rows, {len(raw_data.columns)} columns")
    
    if report_file is not None:
        try:
            # Read all sheets from the Excel file
            excel_file = pd.ExcelFile(report_file)
            report_format = {}
            for sheet_name in excel_file.sheet_names:
                report_format[sheet_name] = pd.read_excel(report_file, sheet_name=sheet_name)
            st.success(f"Report format loaded: {len(excel_file.sheet_names)} sheets")
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
    
    return raw_data, report_format

def create_summary_report(df):
    """Create a summary report from journal entry data"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Clean amount column - convert to numeric
    if 'Amount' in df.columns:
        df['Amount_Numeric'] = pd.to_numeric(df['Amount'].astype(str).str.replace(',', ''), errors='coerce')
    else:
        df['Amount_Numeric'] = 0
    
    # Group by key dimensions for summary
    summary_cols = []
    
    # Check which grouping columns exist
    if 'Account' in df.columns:
        summary_cols.append('Account')
    if 'Department: Name' in df.columns:
        summary_cols.append('Department: Name')
    elif 'Department' in df.columns:
        summary_cols.append('Department')
    if 'Accounting Period: Name' in df.columns:
        summary_cols.append('Accounting Period: Name')
    elif 'Accounting Period' in df.columns:
        summary_cols.append('Accounting Period')
    
    if summary_cols:
        summary = df.groupby(summary_cols).agg({
            'Amount_Numeric': ['sum', 'count'],
            'Number': 'nunique'
        }).round(2)
        
        # Flatten column names
        summary.columns = ['Total_Amount', 'Transaction_Count', 'Unique_Numbers']
        summary = summary.reset_index()
        
        return summary
    else:
        return pd.DataFrame()

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
        
        tab1, tab2 = st.tabs(["Summary Report", "Detailed Report"])
        
        with tab1:
            st.subheader("Summary by Account and Department")
            summary_df = create_summary_report(raw_data)
            if not summary_df.empty:
                st.dataframe(summary_df, use_container_width=True)
                
                # Download option
                csv = summary_df.to_csv(index=False)
                st.download_button(
                    label="Download Summary as CSV",
                    data=csv,
                    file_name="summary_report.csv",
                    mime="text/csv"
                )
            else:
                st.info("Unable to create summary - check column names")
        
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
