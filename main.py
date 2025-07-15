import os
import certifi
import json
import requests
import pandas as pd
from io import StringIO, BytesIO
import asyncio

import boto3
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button
from dotenv import load_dotenv
import botocore

import urllib.parse
from orders_report import OrdersReport
from datetime import datetime, date

# Load environment variables
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

def get_google_oauth_url(discord_id: int) -> str:
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        # Request both read-only access to spreadsheets and drive files so we can list sheets
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly",
        "access_type": "offline",    # to get a refresh token
        "prompt": "consent",         # always prompt so that you get a refresh token on the first run
        "state": str(discord_id)     # pass the Discord user ID in state for later identification
    }
    oauth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return oauth_url

os.environ['SSL_CERT_FILE'] = certifi.where()

# AWS and Discord configuration from environment
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
CONFIG_S3_BUCKET = os.getenv("CONFIG_S3_BUCKET")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
USERS_CONFIG_KEY = "users.json"  # S3 key for the user config file

# Ensure AWS credentials are provided
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise Exception("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file.")

PERMS_KEY = "command_permissions.json"

def get_command_perms():
    s3 = boto3.client('s3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    try:
        body = s3.get_object(Bucket=CONFIG_S3_BUCKET, Key=PERMS_KEY)["Body"].read().decode()
        return json.loads(body)
    except s3.exceptions.NoSuchKey:
        return {}
    except:
        return {}

def update_command_perms(perms):
    s3 = boto3.client('s3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    s3.put_object(Bucket=CONFIG_S3_BUCKET, Key=PERMS_KEY, Body=json.dumps(perms))


# Set up Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        embed = create_embed(
            description="You do not have the required role to use this command.",
            title="Permission Denied",
            color=discord.Color.red()
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        raise error
    
def refresh_access_token(user_record):
    """
    Use the stored refresh_token to get a new access_token.
    Updates user_record["google_tokens"] in S3 if successful.
    Returns the new access_token string.
    """
    refresh_token = user_record["google_tokens"].get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh_token found. User must re-link Google account.")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()
    new_tokens = resp.json()
    # new_tokens typically contains at least "access_token" and "expires_in"
    # Keep the old refresh_token if Google didn't return a new one:
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    # Merge into existing tokens dict so we don't lose any fields
    user_record["google_tokens"].update(new_tokens)
    update_users_config(get_users_config())  # save the merged tokens back to S3
    return new_tokens["access_token"]

def safe_list_spreadsheets(user_record):
    """
    Tries to list spreadsheets using the current access_token.
    If a 401 occurs, refreshes the token once and retries.
    """
    access_token = user_record["google_tokens"]["access_token"]
    try:
        return list_user_spreadsheets(access_token)
    except Exception as e:
        # Detect 401 from the exception message (you could also check response.status_code directly)
        if "401" in str(e) or "Invalid Credentials" in str(e):
            # Refresh and retry
            new_access = refresh_access_token(user_record)
            return list_user_spreadsheets(new_access)
        else:
            # Some other error
            raise

def list_user_spreadsheets(access_token: str) -> list:
    """
    Lists spreadsheets in the user's Google Drive.
    """
    url = "https://www.googleapis.com/drive/v3/files"
    query = "mimeType='application/vnd.google-apps.spreadsheet'"
    params = {"q": query, "fields": "files(id, name)"}
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, params=params, headers=headers)
    if response.ok:
        data = response.json()
        return data.get("files", [])
    else:
        raise Exception(f"Error listing spreadsheets: {response.text}")

def get_sheet_headers(user_record, spreadsheet_id, title) -> list[str]:
    """
    Retrieves the header row (assumed to be the first row) from the specified spreadsheet,
    refreshing the access token once if we get a 401 Unauthorized.
    """
    def _fetch(token):
        range_ = f"'{title}'!A1:Z1"
        url    = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
        headers = {"Authorization": f"Bearer {token}"}
        return requests.get(url, headers=headers)

    # 1) Try with the current access_token
    token = user_record["google_tokens"]["access_token"]
    resp = _fetch(token)

    # 2) If unauthorized, refresh the token and try again
    if resp.status_code == 401:
        token = refresh_access_token(user_record)
        resp = _fetch(token)

    # 3) Now raise for any other error
    resp.raise_for_status()

    # 4) Parse and return the first row (or empty list)
    values = resp.json().get("values", [])
    return values[0] if values else []

def create_embed(
    description: str,
    *,
    title: str = None,
    color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    """
    Creates a Discord Embed with the given description, optional title, and color.
    """
    embed = discord.Embed(description=description, color=color)
    if title:
        embed.title = title
    return embed

###########################################
# Role Checks                             #
###########################################

def has_required_role(interaction: discord.Interaction, allowed_role_ids: list[int]) -> bool:
    user_roles = [role.id for role in interaction.user.roles]
    return any(role_id in user_roles for role_id in allowed_role_ids)

def restrict_to(*static_role_ids):
    def decorator(func):
        async def predicate(interaction: discord.Interaction) -> bool:
            # 1) static roles
            if static_role_ids and any(r.id in static_role_ids for r in interaction.user.roles):
                return True
            # 2) dynamic roles & users from S3
            perms = get_command_perms()
            entry = perms.get(interaction.command.name, {}) or {}
            if any(r.id in entry.get("roles", []) for r in interaction.user.roles):
                return True
            if interaction.user.id in entry.get("users", []):
                return True
            return False
        return app_commands.check(predicate)(func)
    return decorator

###########################################
# S3 Functions for Users Config           #
###########################################

def get_users_config():
    """
    Retrieves the users configuration from S3.
    """
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        return config_data.get("users", [])
    except Exception as e:
        print(f"Error fetching users config: {e}")
        return []

def update_users_config(users):
    """
    Updates the users configuration file in S3.
    """
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    config_data = json.dumps({"users": users})
    try:
        s3_client.put_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY, Body=config_data)
        print("Users configuration updated successfully.")
    except Exception as e:
        print(f"Error updating users config: {e}")

###########################################
# S3 File Uploader (for /upload)          #
###########################################

def upload_file_to_s3(file_bytes, file_name):
    """
    Uploads file bytes to AWS S3 with the specified file name.
    """
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    try:
        s3_client.put_object(Bucket=CONFIG_S3_BUCKET, Key=file_name, Body=file_bytes)
        return f"Successfully uploaded '{file_name}' to bucket."
    except Exception as e:
        return f"Error uploading '{file_name}' to S3: {e}"
    
async def run_mapping_views(required_mapping: list, options: list, interaction: discord.Interaction) -> dict:
    """
    Splits the required mapping list into chunks of up to 5 items.
    For each chunk, sends a mapping view to the user and waits for it to complete.
    Returns a combined dictionary of mapping results.
    """
    mapping_result = {}
    # Process the mapping in chunks of 5 items
    for i in range(0, len(required_mapping), 5):
        chunk = required_mapping[i:i+5]
        view = MappingView(chunk, options)
        embed = create_embed(
            description=f"Map the following required columns: {', '.join(chunk)}",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        mapping_result.update(view.mapping_result)
    return mapping_result

def safe_option_text(text: str) -> str:
    """
    Ensures the provided text is between 1 and 100 characters.
    If text is empty, returns a fallback value.
    If text is longer than 100 characters, trims it and appends '...'
    """
    text = str(text).strip()
    if not text:
        return "Untitled"
    if len(text) > 100:
        return text[:97] + "..."
    return text

def list_worksheets(access_token: str, spreadsheet_id: str) -> list[dict]:
    """
    Returns a list of sheet-tabs in the spreadsheet:
      [ { 'sheetId': xxx, 'title': 'Leads' }, … ]
    """
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    params = { "fields": "sheets(properties(sheetId,title))" }
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    sheets = r.json().get("sheets", [])
    return [s["properties"] for s in sheets]

# ─── EXTRA HELPERS FOR "UNDERPAID REIMBURSEMENTS" ─────────────────────────────

def fetch_all_sheet_titles_for_user(user_record) -> list[str]:
    """
    Uses the stored refresh_token to get a fresh access_token,
    then calls spreadsheets.get?fields=sheets(properties(title))
    to return a list of all worksheet titles in that user's Sheet.
    """
    # 1) Grab a valid access_token (refresh if needed)
    access_token = user_record["google_tokens"]["access_token"]
    # Try one request; if 401, refresh and retry
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{user_record['sheet_id']}?fields=sheets(properties(title))"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 401:
        access_token = refresh_access_token(user_record)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    return [sheet["properties"]["title"] for sheet in data.get("sheets", [])]


def fetch_google_sheet_as_df(user_record, worksheet_title) -> pd.DataFrame:
    """
    Fetches one worksheet's entire A1:ZZ range, pads/truncates rows to match headers,
    and returns a DataFrame with the first row as column names.
    """
    sheet_id = user_record["sheet_id"]
    access_token = user_record["google_tokens"]["access_token"]
    range_ = f"'{worksheet_title}'!A1:ZZ"
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{urllib.parse.quote(range_)}?majorDimension=ROWS"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 401:
        access_token = refresh_access_token(user_record)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    values = resp.json().get("values", [])
    if not values:
        return pd.DataFrame()

    headers_row = values[0]
    records = []
    for row in values[1:]:
        # pad or truncate so len(row) == len(headers_row)
        if len(row) < len(headers_row):
            row = row + [""] * (len(headers_row) - len(row))
        elif len(row) > len(headers_row):
            row = row[: len(headers_row)]
        records.append(row)

    return pd.DataFrame(records, columns=headers_row)


def build_highest_cogs_map_for_user(user_record) -> dict[str, float]:
    """
    Fetches every worksheet title, then for each sheet:
      - normalizes headers to lowercase
      - finds any "asin" column and any "cogs" column (by substring match)
      - strips "$" and commas from COGS, coercing to float
      - groups by ASIN and takes max(COGS)
    Returns a map { asin_string: highest_cogs_float } across all worksheets.
    """
    max_cogs: dict[str, float] = {}
    titles = fetch_all_sheet_titles_for_user(user_record)

    for title in titles:
        df = fetch_google_sheet_as_df(user_record, title)
        if df.empty:
            continue

        # Print debug info if desired:
        # print(f"[DEBUG] Raw headers for '{title}': {list(df.columns)}")

        # lowercase all headers
        df.columns = [c.strip().lower() for c in df.columns]

        # pick first column that contains "asin" and first that contains "cogs"
        asin_cols = [c for c in df.columns if "asin" in c]
        cogs_cols = [c for c in df.columns if "cogs" in c]
        if not asin_cols or not cogs_cols:
            # skip sheets that don't have an ASIN or COGS header
            continue

        asin_col = asin_cols[0]
        cogs_col = cogs_cols[0]

        # strip "$" and commas from COGS, coerce to float
        df[cogs_col] = (
            df[cogs_col]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )
        df[cogs_col] = pd.to_numeric(df[cogs_col], errors="coerce")
        df = df.dropna(subset=[asin_col, cogs_col])
        if df.empty:
            continue

        grouped = df.groupby(asin_col, as_index=False)[cogs_col].max()
        for _, row in grouped.iterrows():
            asin = str(row[asin_col]).strip()
            cogs = float(row[cogs_col])
            if asin in max_cogs:
                if cogs > max_cogs[asin]:
                    max_cogs[asin] = cogs
            else:
                max_cogs[asin] = cogs

    return max_cogs


def filter_underpaid_reimbursements(aura_df: pd.DataFrame, max_cogs_map: dict[str, float]) -> pd.DataFrame:
    """
    Given a DataFrame of reimbursements (with columns including "asin" and "amount-per-unit"),
    returns a new DataFrame containing only rows where 
      (amount-per-unit < max_cogs_map[asin]) and reason != "Reimbursement_Reversal".

    Output columns: 
      reimbursement-id, reason, sku, asin, product-name,
      amount-per-unit, amount-total, quantity-reimbursed-total,
      highest_cogs, shortfall_amount
    """
    # lowercase columns for consistency
    aura_df.columns = [c.strip().lower() for c in aura_df.columns]

    required_cols = {
        "reimbursement-id", "reason", "sku", "asin",
        "product-name", "amount-per-unit", "amount-total", "quantity-reimbursed-total"
    }
    if not required_cols.issubset(set(aura_df.columns)):
        raise ValueError(f"Missing columns {required_cols - set(aura_df.columns)} in reimbursement CSV")

    # parse "amount-per-unit" into float
    def parse_money(x):
        try:
            return float(str(x).replace("$", "").replace(",", "").strip())
        except:
            return None

    aura_df["reimb_amount_per_unit"] = aura_df["amount-per-unit"].apply(parse_money)
    aura_df = aura_df.dropna(subset=["asin", "reimb_amount_per_unit"])

    rows = []
    for _, r in aura_df.iterrows():
        if str(r["reason"]).strip().lower() == "reimbursement_reversal":
            continue
        asin = str(r["asin"]).strip()
        reimb_amt = float(r["reimb_amount_per_unit"])
        highest = max_cogs_map.get(asin)
        if highest is not None and reimb_amt < highest:
            shortfall = round(highest - reimb_amt, 2)
            rows.append({
                "reimbursement-id": r["reimbursement-id"],
                "reason": r["reason"],
                "sku": r["sku"],
                "asin": r["asin"],
                "product-name": r["product-name"],
                "amount-per-unit": r["amount-per-unit"],
                "amount-total": r["amount-total"],
                "quantity-reimbursed-total": r["quantity-reimbursed-total"],
                "highest_cogs": highest,
                "shortfall_amount": shortfall
            })

    cols = [
        "reimbursement-id", "reason", "sku", "asin", "product-name",
        "amount-per-unit", "amount-total", "quantity-reimbursed-total",
        "highest_cogs", "shortfall_amount"
    ]
    return pd.DataFrame(rows, columns=cols)


###########################################
# UI Classes for Column Mapping & Price   #
###########################################

class SheetSelect(discord.ui.Select):
    def __init__(self, sheets_list: list):
        if len(sheets_list) > 25:
            sheets_list = sheets_list[:25]

        seen_vals = set()
        options = []
        for idx, sheet in enumerate(sheets_list):
            label = safe_option_text(sheet["name"])

            value = str(sheet["id"]).strip()
            if len(value) > 100:
                value = value[:97] + "..."

            if value in seen_vals:
                suffix = f"-{idx}"
                max_base = 100 - len(suffix)
                value = value[:max_base] + suffix
            seen_vals.add(value)

            options.append(discord.SelectOption(label=label, value=value))

        super().__init__(
            placeholder="Select your purchase sheet",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_sheet = self.values[0]
        await interaction.response.send_message(
            f"Selected sheet: {self.values[0]}",
            ephemeral=True
        )
        self.view.stop()

class SheetSelectView(discord.ui.View):
    def __init__(self, sheets_list: list):
        super().__init__(timeout=60)
        self.selected_sheet = None
        self.add_item(SheetSelect(sheets_list))

class WorksheetSelect(discord.ui.Select):
    def __init__(self, worksheets: list[dict]):
        # cap to 25 tabs
        if len(worksheets) > 25:
            worksheets = worksheets[:25]

        seen = set()
        options = []
        for idx, ws in enumerate(worksheets):
            label = safe_option_text(ws["title"])
            # use the title as value (truncated + de-duped exactly like ColumnSelect)
            val = ws["title"]
            if len(val) > 100:
                val = val[:97] + "..."
            if val in seen:
                suffix = f"-{idx}"
                val = val[: 100-len(suffix) ] + suffix
            seen.add(val)
            options.append(discord.SelectOption(label=label, value=val))

        super().__init__(
            placeholder="Pick which tab in that spreadsheet",
            min_values=1, max_values=1,
            options=options
        )
        self._worksheets = worksheets

    async def callback(self, interaction: discord.Interaction):
        # find the real sheet by truncated value
        chosen = self.values[0]
        for prop in self._worksheets:
            title = prop["title"]
            # same truncation logic
            cmp = title if len(title) <= 100 else title[:97]+"..."
            if cmp == chosen or cmp.startswith(chosen[:-3]):
                self.view.chosen_sheet_title = prop["title"]
                break

        await interaction.response.send_message(
            f"✅ You picked tab: **{self.view.chosen_sheet_title}**", ephemeral=True
        )
        self.view.stop()

class WorksheetSelectView(View):
    def __init__(self, worksheets):
        super().__init__(timeout=60)
        self.chosen_sheet_title = None
        self.add_item(WorksheetSelect(worksheets))

class ConfirmView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        await interaction.response.send_message("✅ Thanks for confirming. Let's begin column mapping.", ephemeral=True)
        self.stop()

class ColumnSelect(Select):
    def __init__(self, mapping_type: str, options_list: list):
        self.mapping_type = mapping_type
        if len(options_list) > 25:
            options_list = options_list[:25]

        seen_vals = set()
        options = []
        for idx, raw in enumerate(options_list):
            # make sure both label and value are 1–100 chars
            label = safe_option_text(raw)
            val   = safe_option_text(raw)

            if val in seen_vals:
                suffix = f"-{idx}"
                base = val[:100 - len(suffix)]
                val = base + suffix

            seen_vals.add(val)
            options.append(discord.SelectOption(label=label, value=val))

        super().__init__(
            placeholder=f"Select column for {mapping_type}",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.mapping_result[self.mapping_type] = self.values[0]
        embed = create_embed(
            f"Selected **{self.values[0]}** for **{self.mapping_type}**.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if len(self.view.mapping_result) >= len(self.view.missing_types):
            self.view.stop()

class MappingView(View):
    def __init__(self, missing_types: list, options: list):
        super().__init__(timeout=60)
        self.missing_types = missing_types
        self.mapping_result = {}
        for mapping_type in missing_types:
            self.add_item(ColumnSelect(mapping_type, options))

class PriceUpdateView(View):
    def __init__(self):
        super().__init__(timeout=30)
        self.update_all = None  # True/False based on user response

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.primary)
    async def yes_button(self, interaction: discord.Interaction, button: Button):
        self.update_all = True
        embed = create_embed(
            "Prices will be updated for all matching products.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: Button):
        self.update_all = False
        embed = create_embed(
            "Only products missing a price will be updated.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

###########################################
# Slash Commands                          #
###########################################

GUILD_IDS = [1287450087852740699, 1325968966807453716]

lambda_client = boto3.client(
    "lambda",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name="us-east-2"
)

@bot.tree.command(
    name="run_lambda",
    description="Invoke a Lambda or list your functions",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@restrict_to(1341608661822345257)
@app_commands.describe(
    function_name="The name/ARN of the Lambda, or 'list' to enumerate all functions",
    payload="JSON payload (optional when invoking)"
)
async def run_lambda(interaction: discord.Interaction, function_name: str, payload: str = "{}"):
    await interaction.response.defer(ephemeral=True)

    # LIST FUNCTIONS (with region debug + paginator)
    if function_name.lower() in ("list", "__list__", "functions"):
        region = lambda_client.meta.region_name
        try:
            paginator = lambda_client.get_paginator("list_functions")
            funcs = []
            for page in paginator.paginate():
                funcs.extend(page.get("Functions", []))

            if not funcs:
                return await interaction.followup.send(
                    "*(no functions found in this region)*",
                    ephemeral=True
                )

            lines = [f"- `{f['FunctionName']}` ({f['Runtime']})" for f in funcs]
            await interaction.followup.send(
                "Here are your Lambda functions:\n" + "\n".join(lines),
                ephemeral=True
            )
        except botocore.exceptions.ClientError as err:
            code = err.response["Error"]["Code"]
            if code == "AccessDeniedException":
                return await interaction.followup.send(
                    "❌ I lack `ListFunctions` permission in IAM. Please update your policy.",
                    ephemeral=True
                )
            else:
                return await interaction.followup.send(f"❌ Error listing functions: {err}", ephemeral=True)
        return

    # ─── INVOKE FUNCTION ───────────────────────────────────────────────
    try:
        payload_dict = json.loads(payload)
    except json.JSONDecodeError:
        return await interaction.followup.send(
            "❌ Invalid JSON payload. Please provide a valid JSON string.",
            ephemeral=True
        )

    try:
        resp = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload_dict)
        )
        result = json.loads(resp["Payload"].read().decode())
        result_str = json.dumps(result, indent=2)
        if len(result_str) > 1900:
            result_str = result_str[:1900] + "\n…(truncated)"

        embed = create_embed(
            title=f"Invoked `{function_name}`",
            description=f"```json\n{result_str}\n```",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    except botocore.exceptions.ClientError as err:
        code = err.response["Error"]["Code"]
        if code == "AccessDeniedException":
            msg = "❌ I don't have permission to invoke that function. Please update IAM to allow `lambda:InvokeFunction` on it."
        else:
            msg = f"❌ Error invoking Lambda: {err}"
        await interaction.followup.send(msg, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Unexpected error: {e}", ephemeral=True)

@bot.tree.command(name="grant_user_access", description="Grant a user permission to use a command", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to(1341608661822345257)
@app_commands.describe(command_name="Slash command name", user="User to grant")
async def grant_user_access(interaction, command_name: str, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    perms = get_command_perms()
    entry = perms.setdefault(command_name, {"roles": [], "users": []})
    if user.id in entry["users"]:
        return await interaction.followup.send("Already has access.", ephemeral=True)
    entry["users"].append(user.id)
    update_command_perms(perms)
    await interaction.followup.send(f"Granted {user.mention} access to /{command_name}", ephemeral=True)

@bot.tree.command(name="revoke_user_access", description="Revoke a user's permission for a command", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to(1341608661822345257)
@app_commands.describe(command_name="Slash command name", user="User to revoke")
async def revoke_user_access(interaction, command_name: str, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    perms = get_command_perms()
    entry = perms.get(command_name, {"roles": [], "users": []})
    if user.id not in entry["users"]:
        return await interaction.followup.send("User did not have access.", ephemeral=True)
    entry["users"].remove(user.id)
    if not entry["roles"] and not entry["users"]:
        perms.pop(command_name, None)
    update_command_perms(perms)
    await interaction.followup.send(f"Revoked {user.mention}'s access to /{command_name}", ephemeral=True)

@bot.tree.command(
    name="grant_access",
    description="Grant a role permission to use a bot command",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@restrict_to(1341608661822345257)
@app_commands.describe(
    command_name="Name of the slash command (without the slash)",
    role="Role to grant access to (mention or ID)"
)
async def grant_access(interaction: discord.Interaction, command_name: str, role: discord.Role):
    # 1) Defer so Discord shows the spinner
    await interaction.response.defer(ephemeral=True)

    # 2) Read and initialize your permissions map
    perms = get_command_perms()
    entry = perms.setdefault(command_name, {"roles": [], "users": []})

    # 3) If already granted, immediately follow up
    if role.id in entry["roles"]:
        return await interaction.followup.send(
            f"❗ Role {role.mention} already has access to `/{command_name}`.",
            ephemeral=True
        )

    # 4) Add the role and persist to S3
    entry["roles"].append(role.id)
    update_command_perms(perms)

    # 5) Final follow-up stops the spinner and shows success
    await interaction.followup.send(
        f"✅ Granted {role.mention} access to `/{command_name}`.",
        ephemeral=True
    )


@bot.tree.command(
    name="revoke_access",
    description="Revoke a role's permission to use a bot command",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@restrict_to(1341608661822345257)
@app_commands.describe(
    command_name="Name of the slash command (without the slash)",
    role="Role to revoke (mention or ID)"
)
async def revoke_access(interaction: discord.Interaction, command_name: str, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    perms = get_command_perms()
    entry = perms.get(command_name, {"roles": [], "users": []})
    if role.id not in entry["roles"]:
        return await interaction.followup.send(f"❌ {role.mention} doesn't have access to `/{command_name}`.", ephemeral=True)
    entry["roles"].remove(role.id)
    # if no roles **and** no users left, remove the command entirely
    if not entry["roles"] and not entry["users"]:
        perms.pop(command_name, None)
    update_command_perms(perms)
    await interaction.followup.send(f"✅ Revoked {role.mention}'s access to `/{command_name}`.", ephemeral=True)

@bot.tree.command(
    name="list_access",
    description="List which roles and users have access to each slash command",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@restrict_to(1287450087852740705)
async def list_access(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    perms = get_command_perms()  # { "command_name": { "roles":[role_ids], "users":[user_ids] } }
    if not perms:
        return await interaction.followup.send("No custom access rules configured.", ephemeral=True)

    embed = discord.Embed(
        title="Command Access List",
        color=discord.Color.blue(),
        description="Shows which roles and users are permitted to invoke each command."
    )

    for cmd_name, entry in perms.items():
        roles = entry.get("roles", [])
        users = entry.get("users", [])
        # Mention roles/users where possible
        role_mentions = " ".join(f"<@&{r}>" for r in roles) or "—"
        user_mentions = " ".join(f"<@{u}>" for u in users) or "—"
        embed.add_field(
            name=f"/{cmd_name}",
            value=f"**Roles:** {role_mentions}\n**Users:** {user_mentions}",
            inline=False
        )

    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(
    name="list_commands",
    description="List all available slash commands",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@restrict_to(1287450087852740705)
async def list_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="Available Slash Commands",
        color=discord.Color.blue(),
        description="Here are all the slash commands I know:"
    )

    # 1) Global commands
    global_cmds = bot.tree.get_commands(guild=None)
    if global_cmds:
        embed.add_field(name="🌐 Global", value="\n".join(f"/{c.name}" for c in global_cmds), inline=False)

    # 2) Guild-scoped commands
    for gid in GUILD_IDS:
        guild_obj = discord.Object(id=gid)
        guild_cmds = bot.tree.get_commands(guild=guild_obj)
        if guild_cmds:
            embed.add_field(
                name=f"🏠 Guild {gid}",
                value="\n".join(f"/{c.name}" for c in guild_cmds),
                inline=False
            )

    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="complete_google_auth", description="Complete Google OAuth linking by providing the authorization code", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@app_commands.describe(code="The authorization code from Google")
async def complete_google_auth(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=True)
    try:
        # Exchange the authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        token_response = requests.post(token_url, data=payload)
        token_response.raise_for_status()
        tokens = token_response.json()  # contains access_token, refresh_token, etc.

        # Update the user's configuration with the tokens.
        user_id = interaction.user.id
        # …after token_response.raise_for_status()…
        tokens = token_response.json()  # may or may not contain "refresh_token"

        # 1) Load existing users and find (or create) this user's record
        users = get_users_config()
        user_record = next((u for u in users if u.get("discord_id") == user_id), None)
        if user_record is None:
            user_record = {"discord_id": user_id, "google_tokens": {}}
            users.append(user_record)

        # 2) Preserve old refresh_token if Google didn't return a new one
        old_tokens = user_record.get("google_tokens", {})
        if "refresh_token" not in tokens and "refresh_token" in old_tokens:
            tokens["refresh_token"] = old_tokens["refresh_token"]

        # 3) Overwrite the stored tokens (merging refresh_token as needed)
        user_record["google_tokens"] = tokens
        update_users_config(users)

        await interaction.followup.send("Your Google account has been successfully linked! Now run `/setup` again to select your purchase sheet.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error completing Google OAuth: {e}", ephemeral=True)

@bot.tree.command(name="upload", description="Upload a file to S3", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@app_commands.describe(file="The file to upload")
async def slash_upload(interaction: discord.Interaction, file: discord.Attachment):
    """
    Slash command to upload a file to S3.
    """
    try:
        file_bytes = await file.read()
        result = upload_file_to_s3(file_bytes, file.filename)
        embed = create_embed(
            description=result,
            title="S3 Upload Result",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = create_embed(
            description=f"Error processing the file: {e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(
    name="setup",
    description="Setup your profile with your Google account",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@app_commands.describe(receiving_email="Your email address you want results sent to")
async def slash_setup(interaction: discord.Interaction, receiving_email: str):
    # 1) Defer so we can send multiple followups
    await interaction.response.defer(ephemeral=True)

    user_id = interaction.user.id
    users = get_users_config()
    user_record = next((u for u in users if u["discord_id"] == user_id), None)

    # 2) If no tokens yet, send OAuth button & save minimal record
    if not (user_record and user_record.get("google_tokens")):
        oauth_url = get_google_oauth_url(user_id)
        btn = Button(label="Link Google Account", url=oauth_url)
        view = View()
        view.add_item(btn)
        await interaction.followup.send(
            "Click the button to link your Google account. \n**NOTE:** Make sure the account you link has your purchase sheet."
            "\nAfter consenting, you'll get a code—run `/complete_google_auth code:<that-code>` next.",
            view=view,
            ephemeral=True
        )
        if user_record is None:
            users.append({
                "discord_id": user_id, 
                "email": receiving_email,
                "run_scripts": True  # Set run_scripts to true by default
            })
            update_users_config(users)
        return

    # 3) Already linked → list Drive spreadsheets
    tokens = user_record["google_tokens"]
    access_token = tokens["access_token"]
    files = safe_list_spreadsheets(user_record)
    if not files:
        return await interaction.followup.send("No Google Sheets found in your Drive.", ephemeral=True)

    # 4) Show Drive-file picker
    file_view = SheetSelectView(files)
    await interaction.followup.send(
        "Select which **spreadsheet** you'd like to use:",
        view=file_view, ephemeral=True
    )
    await file_view.wait()
    if not file_view.selected_sheet:
        return await interaction.followup.send("No spreadsheet selected. Try `/setup` again.", ephemeral=True)

    spreadsheet_id = file_view.selected_sheet
    user_record["sheet_id"] = spreadsheet_id
    update_users_config(users)

    # 5) List tabs in that spreadsheet
    # 5) List tabs in that spreadsheet (use refresh if 401)
    try:
        worksheets = list_worksheets(access_token, spreadsheet_id)
    except requests.exceptions.HTTPError as e:
        # if it's a 401 Unauthorized, refresh and retry once
        if e.response.status_code == 401:
            new_access = refresh_access_token(user_record)
            worksheets = list_worksheets(new_access, spreadsheet_id)
        else:
            # some other error (e.g. bad spreadsheet ID)
            raise

    if not worksheets:
        return await interaction.followup.send("No tabs found in that spreadsheet.", ephemeral=True)

    ws_view = WorksheetSelectView(worksheets)
    await interaction.followup.send(
        "Now select which **tab** (worksheet) to map:",
        view=ws_view, ephemeral=True
    )
    await ws_view.wait()
    if not ws_view.chosen_sheet_title:
        return await interaction.followup.send("No tab selected. Try `/setup` again.", ephemeral=True)

    worksheet_title = ws_view.chosen_sheet_title
    user_record["worksheet_title"] = worksheet_title
    update_users_config(users)

    # 6) Fetch headers from the chosen worksheet
    headers = get_sheet_headers(user_record, spreadsheet_id, worksheet_title)
    if not headers:
        return await interaction.followup.send(
            "Could not read row 1 from that tab.", ephemeral=True
        )

    # 7) Column mapping (in chunks of 5)
    required_mapping = [
        "Date", "Sale Price", "Name", "Size/Color", "# Units in Bundle",
        "Amount Purchased", "ASIN", "COGS", "Order #", "Prep Notes"
    ]

    confirm_view = ConfirmView()
    confirm_embed = create_embed(
        description=(
            "Before we begin mapping, please make sure your sheet has column that can be mapped to **all** of these:\n\n"
            + "\n".join(f"- **{col}**" for col in required_mapping)
        ),
        title="Required Columns",
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
    await confirm_view.wait()
    if not confirm_view.confirmed:
        return await interaction.followup.send(
            "❌ You did not confirm in time. Please run `/setup` again when you're ready.",
            ephemeral=True
        )
    
    mapping_result = await run_mapping_views(required_mapping, headers, interaction)
    if len(mapping_result) < len(required_mapping):
        return await interaction.followup.send(
            "Mapping timed out or incomplete. Please try `/setup` again.", ephemeral=True
        )

    # 8) Persist profile info so far
    user_record["column_mapping"] = mapping_result
    user_record["email"] = receiving_email
    update_users_config(users)

    # 9) Ask for listing_loader_key
    await interaction.followup.send(
        "Please specify your listing loader key (without the `.xlsm` extension):",
        ephemeral=True
    )

    def check(m: discord.Message):
        return (
            m.author.id == user_id
            and m.channel == interaction.channel
            and not m.author.bot
        )

    try:
        msg: discord.Message = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        return await interaction.followup.send(
            "⏰ Timeout: you took too long to respond. Please run `/setup` again to finish configuration.",
            ephemeral=True
        )

    loader_key = msg.content.strip()
    if not loader_key.lower().endswith(".xlsm"):
        loader_key += ".xlsm"
    user_record["listing_loader_key"] = loader_key
    update_users_config(users)

    await interaction.followup.send(
        "Please specify your **sellerboard** file key (without the `.xlsx` extension):",
        ephemeral=True
    )

    try:
        sb_msg: discord.Message = await bot.wait_for("message", check=check, timeout=60)
    except asyncio.TimeoutError:
        return await interaction.followup.send(
            "⏰ Timeout: you took too long to provide your sellerboard file key. Please run `/setup` again to finish configuration.",
            ephemeral=True
        )

    sb_file_key = sb_msg.content.strip()
    if not sb_file_key.lower().endswith(".xlsx"):
        sb_file_key += ".xlsx"
    user_record["sb_file_key"] = sb_file_key
    update_users_config(users)
    
    await interaction.followup.send(
        f"🎉 Setup complete!\n"
        f"• Listing loader: `{loader_key}`\n"
        f"• Sellerboard file: `{sb_file_key}`\n\n"
        "I'll now use your linked sheet, tab, column map, loader file, and sellerboard file for all future commands.",
        ephemeral=True
    )

@bot.tree.command(name="removeprofile", description="Remove your profile from the system", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
async def slash_removeprofile(interaction: discord.Interaction):
    """
    Remove the sheet associated with your Discord user ID.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = interaction.user.id
        users = get_users_config()

        # Find and remove your record
        index_to_remove = None
        for idx, user in enumerate(users):
            if user.get("discord_id") == user_id:
                index_to_remove = idx
                break

        if index_to_remove is None:
            embed = create_embed(
                "No profile found for your user ID. Nothing to remove.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        removed_entry = users.pop(index_to_remove)
        update_users_config(users)
        embed = create_embed(
            description=(
                f"Successfully removed your profile:"
                f"\nEmail: {removed_entry.get('receiving_email')}"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        embed = create_embed(
            description=f"Error removing your configuration: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(
    name="find_underpaid",
    description="Find underpaid reimbursements by comparing your uploaded CSV to your Google Sheet's max COGS",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@app_commands.describe(
    reimbursement_file="Attach the reimbursement CSV to check"
)
async def slash_find_underpaid(interaction: discord.Interaction, reimbursement_file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    # 1) Load the user's record from S3
    user_id = interaction.user.id
    users = get_users_config()
    user_record = next((u for u in users if u.get("discord_id") == user_id), None)
    if not user_record or not user_record.get("sheet_id") or not user_record.get("worksheet_title"):
        return await interaction.followup.send(
            "No Google Sheet linked to your account. Please run `/setup` first.", ephemeral=True
        )

    try:
        blob = await reimbursement_file.read()
        try:
            reimburse_df = pd.read_csv(BytesIO(blob), encoding="utf-8")
        except UnicodeDecodeError:
            # fallback if it isn't valid UTF-8
            reimburse_df = pd.read_csv(BytesIO(blob), encoding="latin-1")
    except Exception as e:
        return await interaction.followup.send(f"Error reading CSV: {e}", ephemeral=True)


    # 3) Build the max-COGS map
    try:
        max_map = build_highest_cogs_map_for_user(user_record)
    except Exception as e:
        return await interaction.followup.send(f"Error fetching your Sheet data: {e}", ephemeral=True)

    if not max_map:
        return await interaction.followup.send(
            "Could not find any COGS data in your Google Sheet's worksheets.", ephemeral=True
        )

    # 4) Filter for underpaid rows
    try:
        underpaid_df = filter_underpaid_reimbursements(reimburse_df, max_map)
    except Exception as e:
        return await interaction.followup.send(f"Error processing reimbursements: {e}", ephemeral=True)

    if underpaid_df.empty:
        return await interaction.followup.send("No underpaid reimbursements found.", ephemeral=True)

    # 5) Convert result to CSV and send back as a file
    out_buf = StringIO()
    underpaid_df.to_csv(out_buf, index=False)
    out_bytes = out_buf.getvalue().encode("utf-8")
    discord_file = discord.File(fp=BytesIO(out_bytes), filename="underpaid_reimbursements.csv")

    embed = create_embed(
        description=f"Found {len(underpaid_df)} underpaid reimbursement(s). Sending file...",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, file=discord_file, ephemeral=True)

@bot.tree.command(
    name="updateaura",
    description="Update aura CSV with cost data from your associated Google Sheet",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@app_commands.describe(aura_file="The aura CSV file to update")
async def slash_updateaura(interaction: discord.Interaction, aura_file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    # 1) Load user_record and confirm sheet_id + worksheet_title exist
    user_id = interaction.user.id
    users = get_users_config()
    user_record = next((u for u in users if u.get("discord_id") == user_id), None)

    # *** instead of checking "sheet", check "sheet_id" and "worksheet_title" ***
    if not user_record or not user_record.get("sheet_id") or not user_record.get("worksheet_title"):
        return await interaction.followup.send(
            "No associated Google Sheet found for your account. Please run `/setup` again.",
            ephemeral=True
        )

    sheet_id = user_record["sheet_id"]
    worksheet_title = user_record["worksheet_title"]

    # 2) Read the aura CSV file the user just uploaded
    try:
        aura_bytes = await aura_file.read()
        aura_df = pd.read_csv(StringIO(aura_bytes.decode("utf-8")))
    except Exception as e:
        return await interaction.followup.send(
            f"Error reading the aura CSV you uploaded: {e}", ephemeral=True
        )

    # 3) Fetch the entire Google Sheet tab via Sheets API
    #    (This uses the same access_token / refresh logic you already have.)
    try:
        access_token = user_record["google_tokens"]["access_token"]
        # Build a GET to Sheets API to fetch the whole sheet as CSV. You can use the "values" endpoint:
        csv_url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
            f"/values/{urllib.parse.quote(worksheet_title)}?majorDimension=ROWS&valueRenderOption=UNFORMATTED_VALUE"
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(csv_url, headers=headers)
        if resp.status_code == 401:
            # token expired → refresh and retry
            new_access = refresh_access_token(user_record)
            headers = {"Authorization": f"Bearer {new_access}"}
            resp = requests.get(csv_url, headers=headers)

        resp.raise_for_status()
        sheet_json = resp.json()
        values = sheet_json.get("values", [])
        if len(values) < 2:
            # no data beyond the header row
            return await interaction.followup.send(
                "Your Google sheet didn't contain any rows beyond the header.", ephemeral=True
            )

        # After you fetch `values = sheet_json.get("values", [])`:
        columns = values[0]
        rows = values[1:]

        # Ensure every row has exactly len(columns) entries:
        max_len = len(columns)
        normalized_rows = []
        for r in rows:
            if len(r) < max_len:
                # pad missing cells with empty strings
                r = r + [""] * (max_len - len(r))
            elif len(r) > max_len:
                # truncate any extra cells
                r = r[:max_len]
            normalized_rows.append(r)

        sheet_df = pd.DataFrame(normalized_rows, columns=columns)

    except Exception as e:
        return await interaction.followup.send(
            f"Error fetching data from your Google Sheet: {e}", ephemeral=True
        )

    # 4) Find which columns correspond to ASIN and COGS, prompting if needed
    sheet_columns = list(sheet_df.columns)
    columns_lower = {col.lower(): col for col in sheet_columns}
    mapping = {}
    missing = []
    if "asin" in columns_lower:
        mapping["ASIN"] = columns_lower["asin"]
    else:
        missing.append("ASIN")
    if "cogs" in columns_lower:
        mapping["COGS"] = columns_lower["cogs"]
    else:
        missing.append("COGS")

    if missing:
        view = MappingView(missing, sheet_columns)
        embed = create_embed(
            description=(
                f"Please select the correct column for **{', '.join(missing)}** "
                "from your Google Sheet:"
            ),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if not view.mapping_result or len(view.mapping_result) < len(missing):
            return await interaction.followup.send(
                "Column mapping not completed in time. Please try again.", ephemeral=True
            )
        mapping.update(view.mapping_result)

    # 5) Normalize and merge COGS data into the aura_df
    try:
        sheet_df = sheet_df.rename(columns={mapping["ASIN"]: "ASIN", mapping["COGS"]: "COGS"})
        sheet_df["ASIN"] = sheet_df["ASIN"].astype(str).str.strip()
        sheet_df["COGS"] = (
            sheet_df["COGS"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        ).astype(float)
    except Exception as e:
        return await interaction.followup.send(
            f"Error processing columns in your Google Sheet: {e}", ephemeral=True
        )

    if "asin" not in aura_df.columns or "cost" not in aura_df.columns:
        return await interaction.followup.send(
            "Your aura CSV must have both 'asin' and 'cost' columns.", ephemeral=True
        )

    aura_df["asin"] = aura_df["asin"].astype(str).str.strip()
    aura_df["cost"] = pd.to_numeric(aura_df["cost"], errors="coerce")

    # 6) Ask user whether to overwrite all or only missing cost values
    price_view = PriceUpdateView()
    prompt_embed = create_embed(
        description=(
            "Do you want to update prices for all matching products?\n"
            "**Yes**: overwrite all costs\n"
            "**No**: only fill in missing costs"
        ),
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=prompt_embed, view=price_view, ephemeral=True)
    await price_view.wait()

    if price_view.update_all is None:
        return await interaction.followup.send(
            "Timed out waiting for your choice. Try `/updateaura` again.", ephemeral=True
        )

    # 7) Perform the actual merging
    updated_rows = []
    for idx, row in aura_df.iterrows():
        match = sheet_df[sheet_df["ASIN"] == row["asin"]]
        if not match.empty:
            new_cost = match.iloc[0]["COGS"]
            if price_view.update_all or pd.isna(row["cost"]):
                if not pd.isna(new_cost):
                    old_cost = row["cost"]
                    aura_df.at[idx, "cost"] = new_cost
                    updated_rows.append({"index": idx, "asin": row["asin"], "old_cost": old_cost, "new_cost": new_cost})

    # 8) Send back a new CSV with updated "cost" column
    output_buffer = StringIO()
    aura_df.to_csv(output_buffer, index=False)
    output_bytes = output_buffer.getvalue().encode("utf-8")

    embed_summary = create_embed(
        description=f"Updated **{len(updated_rows)}** row(s) in the aura CSV file.",
        title="Aura CSV Update Summary",
        color=discord.Color.green()
    )
    file = discord.File(fp=BytesIO(output_bytes), filename="aura_updated.csv")
    await interaction.followup.send(embed=embed_summary, ephemeral=True)

    if updated_rows:
        await interaction.user.send("Here's your updated aura CSV:", file=file)

@bot.tree.command(
    name="toggle_scripts",
    description="Toggle whether your scripts are active",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
async def slash_toggle_scripts(interaction: discord.Interaction):
    """
    Toggle whether your scripts are active.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = interaction.user.id
        users = get_users_config()
        user_record = next((u for u in users if u.get("discord_id") == user_id), None)

        if not user_record:
            return await interaction.followup.send(
                "No profile found. Please run `/setup` first.",
                ephemeral=True
            )

        # Toggle the run_scripts status
        current_status = user_record.get("run_scripts", False)
        user_record["run_scripts"] = not current_status
        update_users_config(users)

        status_text = "activated" if not current_status else "deactivated"
        embed = create_embed(
            description=f"Your scripts have been {status_text}.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        embed = create_embed(
            description=f"Error toggling scripts: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(
    name="orders_report",
    description="Get a summary of ASINs sold for a specific date (defaults to today)",
    guilds=[discord.Object(id=gid) for gid in GUILD_IDS]
)
@app_commands.describe(
    report_date="Date in YYYY-MM-DD format (optional, defaults to today)"
)
async def orders_report_command(interaction: discord.Interaction, report_date: str = None):
    await interaction.response.defer(ephemeral=True)
    try:
        if report_date:
            try:
                for_date = datetime.strptime(report_date, "%Y-%m-%d").date()
            except ValueError:
                return await interaction.followup.send(
                    f"❌ Invalid date format. Please use YYYY-MM-DD.", ephemeral=True
                )
        else:
            for_date = date.today()
        report = OrdersReport()
        df = report.download_csv_report()
        asin_counts = report.process_orders(df, for_date=for_date)
        embed_data = report.make_summary_embed(asin_counts, for_date)
        embed = discord.Embed(
            title=embed_data["title"],
            description=embed_data["description"],
            color=embed_data["color"]
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

###########################################
# on_ready Event                          #
###########################################

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("Cleared global commands.")

        for gid in GUILD_IDS:
            guild_obj = discord.Object(id=gid)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"Synced {len(synced)} commands to guild {gid}.")
            
    except Exception as e:
        print(e)

bot.run(DISCORD_TOKEN)
