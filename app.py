from flask import Flask, render_template
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Google Sheet ID and range
SHEET_ID = '1-U5zFNSJDu2IEqHK9FfcsPlWnOyUY2hFlwykgLIsVjw'
RANGE_NAME = 'Sheet1!A:M'  # Extended to include Bank column

def get_google_sheet_data():
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=RANGE_NAME
        ).execute()
        values = result.get('values', [])

        if not values:
            return None, "No data found in the Google Sheet."

        # Clean headers
        headers = [h.strip() for h in values[0]]
        data = values[1:]
        df = pd.DataFrame(data, columns=headers)

        # Ensure all expected columns exist
        for col in ['Start Date', 'Term', 'Interest Rate', 'Principal', 'Frequency', 'Bank']:
            if col not in df.columns:
                df[col] = None  # fill with NaN if missing

        # Convert data types
        df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
        for col in ['Term', 'Interest Rate', 'Principal']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df, None

    except FileNotFoundError:
        return None, "Service account credentials file (credentials.json) not found."
    except HttpError as e:
        return None, f"Google Sheets API error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error reading Google Sheet: {str(e)}"

def calculate_interest(df):
    today = datetime.now()

    def get_interval(row):
        """Return months between interest payments based on frequency."""
        frequency = str(row.get('Frequency', '')).strip()
        if frequency == "Monthly":
            return 1
        elif frequency == "Quarterly":
            return 3
        elif frequency == "End of Term":
            return row['Term'] if pd.notna(row['Term']) else None
        return None

    def next_interest_date(start_date, term_months, interval_months):
        """Find next interest payment date from today."""
        if interval_months is None or pd.isna(start_date) or pd.isna(term_months):
            return "Invalid Data"

        months_since_start = (today.year - start_date.year) * 12 + (today.month - start_date.month)
        next_multiple = ((months_since_start // interval_months) + 1) * interval_months
        next_date = start_date + relativedelta(months=next_multiple)
        end_date = start_date + relativedelta(months=term_months)

        if next_date > end_date:
            return "Term Ended"
        return next_date.strftime('%Y-%m-%d')

    # Calculate months per payment interval
    df['Interval (months)'] = df.apply(get_interval, axis=1)

    # Next payment date
    df['Next Interest Date'] = df.apply(
        lambda row: next_interest_date(
            row['Start Date'],
            row['Term'],
            row['Interval (months)']
        ), axis=1
    )

    # Interest calculation — annual rate converted for payment interval
    df['Interest Amount'] = df.apply(
        lambda row: 0
        if row['Next Interest Date'] in ["Term Ended", "Invalid Data"]
        or pd.isna(row['Principal'])
        or pd.isna(row['Interest Rate'])
        else row['Principal'] * (row['Interest Rate'] / 100) * (row['Interval (months)'] / 12),
        axis=1
    )

    # Precompute display values for HTML
    df['StartDateDisplay'] = df['Start Date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else 'N/A')
    df['TermDisplay'] = df['Term'].apply(lambda x: int(x) if pd.notna(x) else 'N/A')
    df['InterestRateDisplay'] = df['Interest Rate'].apply(lambda x: round(x, 2) if pd.notna(x) else 'N/A')
    df['PrincipalDisplay'] = df['Principal'].apply(lambda x: round(x, 2) if pd.notna(x) else 'N/A')
    df['IntervalDisplay'] = df['Interval (months)'].apply(lambda x: int(x) if pd.notna(x) else 'N/A')
    df['InterestAmountDisplay'] = df['Interest Amount'].apply(lambda x: round(x, 2) if pd.notna(x) else 0.00)
    df['BankDisplay'] = df['Bank'].apply(lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else 'N/A')

    return df

@app.route('/', methods=['GET'])
def index():
    df, error_message = get_google_sheet_data()
    if df is not None:
        try:
            df = calculate_interest(df)
            data = df.to_dict(orient='records')
            return render_template('index.html', data=data, error=None)
        except Exception as e:
            return render_template('index.html', data=None, error=f"Error processing data: {str(e)}")
    else:
        return render_template('index.html', data=None, error=error_message)

if __name__ == '__main__':
    app.run(debug=True)
