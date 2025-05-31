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

import urllib.parse

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

def get_sheet_headers(access_token, spreadsheet_id, title) -> list[str]:
    """
    Retrieves the header row (assumed to be the first row) from the specified spreadsheet.
    """
    range_ = f"'{title}'!A1:Z1"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.ok:
        data = response.json()
        values = data.get("values", [])
        if values:
            return values[0]
        else:
            return []
    else:
        raise Exception(f"Error reading sheet headers: {response.text}")

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

def restrict_to_roles(*role_ids):
    """
    Decorator that checks if the invoking user has at least one of the allowed roles.
    """
    def predicate(interaction: discord.Interaction) -> bool:
        return has_required_role(interaction, list(role_ids))
    return app_commands.check(predicate)

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
    Returns a list of sheet‐tabs in the spreadsheet:
      [ { 'sheetId': xxx, 'title': 'Leads' }, … ]
    """
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    params = { "fields": "sheets(properties(sheetId,title))" }
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    sheets = r.json().get("sheets", [])
    return [s["properties"] for s in sheets]

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
            # use the title as value (truncated + de‑duped exactly like ColumnSelect)
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
        await interaction.response.send_message("✅ Thanks for confirming. Let’s begin column mapping.", ephemeral=True)
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

@bot.tree.command(name="complete_google_auth", description="Complete Google OAuth linking by providing the authorization code", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to_roles(1341608661822345257, 1287450087852740702)
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
        users = get_users_config()
        user_record = next((user for user in users if user.get("discord_id") == user_id), None)
        if user_record is None:
            # Create a minimal record if it does not exist.
            user_record = {"discord_id": user_id}
            users.append(user_record)
        user_record["google_tokens"] = tokens
        update_users_config(users)

        await interaction.followup.send("Your Google account has been successfully linked! Now run `/setup` again to select your purchase sheet.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error completing Google OAuth: {e}", ephemeral=True)

@bot.tree.command(name="upload", description="Upload a file to S3", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to_roles(1341608661822345257)
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
@restrict_to_roles(1341608661822345257, 1287450087852740702)
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
            "\nAfter consenting, you'll get a code—run `/complete_google_auth code:<that‑code>` next.",
            view=view,
            ephemeral=True
        )
        if user_record is None:
            users.append({"discord_id": user_id, "email": receiving_email})
            update_users_config(users)
        return

    # 3) Already linked → list Drive spreadsheets
    tokens = user_record["google_tokens"]
    access_token = tokens["access_token"]
    files = list_user_spreadsheets(access_token)
    if not files:
        return await interaction.followup.send("No Google Sheets found in your Drive.", ephemeral=True)

    # 4) Show Drive-file picker
    file_view = SheetSelectView(files)
    await interaction.followup.send(
        "Select which **spreadsheet** you’d like to use:",
        view=file_view, ephemeral=True
    )
    await file_view.wait()
    if not file_view.selected_sheet:
        return await interaction.followup.send("No spreadsheet selected. Try `/setup` again.", ephemeral=True)

    spreadsheet_id = file_view.selected_sheet
    user_record["sheet_id"] = spreadsheet_id
    update_users_config(users)

    # 5) List tabs in that spreadsheet
    worksheets = list_worksheets(access_token, spreadsheet_id)
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
    headers = get_sheet_headers(access_token, spreadsheet_id, worksheet_title)
    if not headers:
        return await interaction.followup.send(
            "Could not read row 1 from that tab.", ephemeral=True
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
            "❌ You did not confirm in time. Please run `/setup` again when you’re ready.",
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
        "I’ll now use your linked sheet, tab, column map, loader file, and sellerboard file for all future commands.",
        ephemeral=True
    )

@bot.tree.command(name="removeprofile", description="Remove your profile from the system", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to_roles(1341608661822345257, 1287450087852740702)
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

@bot.tree.command(name="updateaura", description="Update aura CSV with cost data from your associated Google Sheet", guilds=[discord.Object(id=gid) for gid in GUILD_IDS])
@restrict_to_roles(1341608661822345257, 1287450087852740702)
@app_commands.describe(aura_file="The aura CSV file to update")
async def slash_updateaura(interaction: discord.Interaction, aura_file: discord.Attachment):
    """
    Updates an aura CSV file using cost data from the Google Sheet associated with your Discord account.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        # Retrieve your associated sheet link from users.json
        user_id = interaction.user.id
        users = get_users_config()
        user_record = next((user for user in users if user.get("discord_id") == user_id), None)
        if not user_record or not user_record.get("sheet"):
            embed = create_embed(
                "No associated Google Sheet found for your account. Please upload one using `/uploadsheet`.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        google_sheet_url = user_record.get("sheet")

        # Read the aura CSV file
        aura_bytes = await aura_file.read()
        aura_df = pd.read_csv(StringIO(aura_bytes.decode('utf-8')))
    except Exception as e:
        embed = create_embed(
            f"Error reading aura CSV file or retrieving your sheet: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Fetch the Google Sheet data
    try:
        response = requests.get(google_sheet_url)
        response.raise_for_status()
        csv_data = StringIO(response.text)
        sheet_df = pd.read_csv(csv_data, dtype=str)
    except Exception as e:
        embed = create_embed(
            f"Error fetching Google Sheet data: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Auto-detect mapping for ASIN and COGS (case-insensitive)
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
                "from the Google Sheet:"
            ),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        if not view.mapping_result or len(view.mapping_result) < len(missing):
            embed = create_embed(
                "Column mapping not completed in time. Please try the command again.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        mapping.update(view.mapping_result)

    try:
        sheet_df = sheet_df.rename(columns={mapping["ASIN"]: "ASIN", mapping["COGS"]: "COGS"})
        sheet_df["ASIN"] = sheet_df["ASIN"].astype(str).str.strip()
        sheet_df["COGS"] = (
            sheet_df["COGS"]
            .astype(str)
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
        )
        sheet_df["COGS"] = pd.to_numeric(sheet_df["COGS"], errors='coerce')
    except Exception as e:
        embed = create_embed(
            f"Error processing Google Sheet data: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Ensure aura CSV has required headers
    if "asin" not in aura_df.columns or "cost" not in aura_df.columns:
        embed = create_embed(
            "The aura CSV file must have both 'asin' and 'cost' columns.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    aura_df["asin"] = aura_df["asin"].astype(str).str.strip()
    aura_df["cost"] = pd.to_numeric(aura_df["cost"], errors='coerce')

    # Ask user whether to update all prices or only missing ones
    price_view = PriceUpdateView()
    prompt_embed = create_embed(
        description=(
            "Do you want to update prices for all matching products?\n"
            "**Yes**: update all\n"
            "**No**: update only missing prices"
        ),
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=prompt_embed, view=price_view, ephemeral=True)
    await price_view.wait()

    if price_view.update_all is None:
        embed = create_embed(
            "Price update selection not made in time. Aborting command.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    updated_rows = []
    for idx, row in aura_df.iterrows():
        match = sheet_df[sheet_df["ASIN"] == row["asin"]]
        if not match.empty:
            new_cost = match.iloc[0]["COGS"]
            if price_view.update_all or pd.isna(row["cost"]):
                if not pd.isna(new_cost):
                    aura_df.at[idx, "cost"] = new_cost
                    updated_rows.append({
                        "index": idx,
                        "asin": row["asin"],
                        "old_cost": row["cost"],
                        "new_cost": new_cost
                    })

    output_buffer = StringIO()
    aura_df.to_csv(output_buffer, index=False)
    output_bytes = output_buffer.getvalue().encode('utf-8')

    embed_summary = create_embed(
        description=f"Updated **{len(updated_rows)}** row(s) in the aura CSV file.",
        title="Aura CSV Update Summary",
        color=discord.Color.green()
    )
    file = discord.File(fp=BytesIO(output_bytes), filename="aura_updated.csv")
    await interaction.followup.send(embed=embed_summary, ephemeral=True)

    if updated_rows:
        await interaction.user.send("Aura Updated File", file=file)

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
