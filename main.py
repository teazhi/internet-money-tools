import os
import certifi
import json
import requests
import pandas as pd
from io import StringIO, BytesIO

import boto3
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button
from dotenv import load_dotenv

# Point to the certifi certificate bundle (useful on macOS)
os.environ['SSL_CERT_FILE'] = certifi.where()

# Load environment variables
load_dotenv()

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
    Expected format: 
    {
      "users": [
        {
          "discord_id": 123456789,
          "sheet": "https://docs.google.com/...",
          "email": "user@example.com"
        },
        ...
      ]
    }
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
        return f"Successfully uploaded '{file_name}' to bucket '{CONFIG_S3_BUCKET}'."
    except Exception as e:
        return f"Error uploading '{file_name}' to S3: {e}"

###########################################
# UI Classes for Column Mapping & Price   #
###########################################

class ColumnSelect(Select):
    def __init__(self, mapping_type: str, options_list: list):
        self.mapping_type = mapping_type
        options = [discord.SelectOption(label=col, value=col) for col in options_list]
        super().__init__(
            placeholder=f"Select column for {mapping_type}",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.mapping_result[self.mapping_type] = self.values[0]
        await interaction.response.send_message(
            f"Selected **{self.values[0]}** for **{self.mapping_type}**.", ephemeral=True
        )
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
        await interaction.response.send_message("Prices will be updated for all matching products.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, button: Button):
        self.update_all = False
        await interaction.response.send_message("Only products missing a price will be updated.", ephemeral=True)
        self.stop()

###########################################
# Slash Commands                          #
###########################################

GUILD_ID = 1287450087852740699  # Replace with your guild ID if needed

@bot.tree.command(name="upload", description="Upload a file to S3", guild=discord.Object(id=GUILD_ID))
@restrict_to_roles(1341608661822345257)
@app_commands.describe(file="The file to upload")
async def slash_upload(interaction: discord.Interaction, file: discord.Attachment):
    """
    Slash command to upload a file to S3.
    """
    try:
        file_bytes = await file.read()
        result = upload_file_to_s3(file_bytes, file.filename)
        embed = discord.Embed(
            title="S3 Upload Result",
            description=result,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Error processing the file: {e}", ephemeral=True)


@bot.tree.command(name="uploadsheet", description="Upload or update your Google Sheet link and email", guild=discord.Object(id=GUILD_ID))
@restrict_to_roles(1341608661822345257, 1287450087852740702)
@app_commands.describe(
    sheet_link="Your Google Sheet CSV URL",
    email="Your email address"
)
async def slash_uploadsheet(interaction: discord.Interaction, sheet_link: str, email: str):
    """
    Each Discord user can only have one sheet. If the user's discord_id is already in the config,
    we throw an error. The user must remove their sheet before uploading a new one.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = interaction.user.id
        users = get_users_config()

        # Check if this user_id already has a sheet
        for user in users:
            if user.get("discord_id") == user_id:
                await interaction.followup.send(
                    "You already have a sheet associated. Please remove it first using `/removesheet`.",
                    ephemeral=True
                )
                return

        # If no entry for this user, create one
        users.append({
            "discord_id": user_id,
            "sheet": sheet_link,
            "email": email
        })
        update_users_config(users)
        await interaction.followup.send(
            f"Your sheet link and email have been added. (Discord ID: {user_id})",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"Error updating your configuration: {e}", ephemeral=True)


@bot.tree.command(name="removesheet", description="Remove your sheet link from the system", guild=discord.Object(id=GUILD_ID))
@restrict_to_roles(1341608661822345257, 1287450087852740702)
async def slash_removesheet(interaction: discord.Interaction):
    """
    Remove the sheet associated with your Discord user ID.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = interaction.user.id
        users = get_users_config()

        # Find the user entry by discord_id
        index_to_remove = None
        for idx, user in enumerate(users):
            if user.get("discord_id") == user_id:
                index_to_remove = idx
                break

        if index_to_remove is None:
            await interaction.followup.send(
                "No sheet found for your user ID. Nothing to remove.",
                ephemeral=True
            )
            return

        # Remove the user's entry
        removed_entry = users.pop(index_to_remove)
        update_users_config(users)
        await interaction.followup.send(
            f"Removed your sheet: {removed_entry.get('sheet')} (Email: {removed_entry.get('email')})",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"Error removing your configuration: {e}", ephemeral=True)


@bot.tree.command(name="updateaura", description="Update aura CSV with cost data from a Google Sheet", guild=discord.Object(id=GUILD_ID))
@restrict_to_roles(1341608661822345257, 1287450087852740702)
@app_commands.describe(
    aura_file="The aura CSV file to update",
    google_sheet_url="Optional: Google Sheet URL containing cost data"
)
async def slash_updateaura(interaction: discord.Interaction, aura_file: discord.Attachment, google_sheet_url: str = None):
    """
    Slash command to update an aura CSV file using cost data from a Google Sheet.
    """
    await interaction.response.defer()
    try:
        aura_bytes = await aura_file.read()
        aura_df = pd.read_csv(StringIO(aura_bytes.decode('utf-8')))
    except Exception as e:
        await interaction.followup.send(f"Error reading aura CSV file: {e}", ephemeral=True)
        return

    if not google_sheet_url:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
            google_sheet_url = config.get("google_sheet_url", "").strip()
        if not google_sheet_url:
            await interaction.followup.send("Google Sheet URL not provided and no config.json found.", ephemeral=True)
            return

    try:
        response = requests.get(google_sheet_url)
        response.raise_for_status()
        csv_data = StringIO(response.text)
        sheet_df = pd.read_csv(csv_data, dtype=str)
    except Exception as e:
        await interaction.followup.send(f"Error fetching Google Sheet data: {e}", ephemeral=True)
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
        prompt_msg = f"Please select the correct column for **{', '.join(missing)}** from the Google Sheet:"
        await interaction.followup.send(prompt_msg, view=view, ephemeral=True)
        await view.wait()
        if not view.mapping_result or len(view.mapping_result) < len(missing):
            await interaction.followup.send("Column mapping not completed in time. Please try the command again.", ephemeral=True)
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
        await interaction.followup.send(f"Error processing Google Sheet data: {e}", ephemeral=True)
        return

    # Check required headers in aura CSV
    if "asin" not in aura_df.columns or "cost" not in aura_df.columns:
        await interaction.followup.send("The aura CSV file must have both 'asin' and 'cost' columns.", ephemeral=True)
        return
    aura_df["asin"] = aura_df["asin"].astype(str).str.strip()
    aura_df["cost"] = pd.to_numeric(aura_df["cost"], errors='coerce')

    # Ask user if they want to update prices for all products
    price_view = PriceUpdateView()
    prompt = "Do you want to update prices for all matching products? (Yes: update all; No: update only missing prices)"
    await interaction.followup.send(prompt, view=price_view, ephemeral=True)
    await price_view.wait()

    if price_view.update_all is None:
        await interaction.followup.send("Price update selection not made in time. Aborting command.", ephemeral=True)
        return

    updated_rows = []
    # Update rows based on user's selection
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

    embed = discord.Embed(
        title="Aura CSV Update Summary",
        description=f"Updated **{len(updated_rows)}** row(s) in the aura CSV file.",
        color=discord.Color.green()
    )
    file = discord.File(fp=BytesIO(output_bytes), filename="aura_updated.csv")
    await interaction.followup.send(embed=embed, ephemeral=True)

    if updated_rows:
        await interaction.user.send("Aura Updated File", file=file)

###########################################
# on_ready Event                          #
###########################################

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    guild = discord.Object(id=GUILD_ID)
    try:
        # Clear any previously registered global commands
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("Cleared global commands.")

        # Now sync guild commands only
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to guild {guild.id}.")
    except Exception as e:
        print(e)

bot.run(DISCORD_TOKEN)
