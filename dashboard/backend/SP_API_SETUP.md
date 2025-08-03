# SP-API Integration Setup Guide

This document explains how to set up Amazon Seller Partner API (SP-API) integration to replace Sellerboard data.

## Prerequisites

1. **Amazon Seller Central Account** with SP-API access
2. **Developer Account** registered with Amazon
3. **SP-API Application** created and approved

## Step 1: Create SP-API Application

1. Go to [Amazon Developer Console](https://developer.amazon.com/)
2. Sign in with your developer account
3. Navigate to "Login with Amazon" → "Create a New Security Profile"
4. Fill in your application details:
   - **Security Profile Name**: "Your Business Name - Dashboard"
   - **Security Profile Description**: "Analytics dashboard for Amazon seller data"
   - **Consent Privacy Notice URL**: Your privacy policy URL
   - **Consent Logo Image**: Your company logo

5. Note down the **Client ID** and **Client Secret**

## Step 2: Get SP-API Access

1. Go to [Seller Central](https://sellercentral.amazon.com/)
2. Navigate to Apps & Services → Develop apps for Amazon
3. Click "Add new app client"
4. Enter your **LWA Client ID** from Step 1
5. Select the required roles:
   - **View and manage orders**
   - **View inventory**
   - **View sales data** 
   - **View reports**

## Step 3: Obtain Refresh Token

1. Use the SP-API authorization workflow to get a refresh token
2. This involves redirecting users through Amazon's OAuth flow
3. The refresh token is long-lived and doesn't expire

**For testing/development**, you can use the SP-API sandbox:
- Follow the [SP-API Developer Guide](https://developer-docs.amazon.com/sp-api/docs)
- Use sandbox endpoints for testing

## Step 4: Configure Environment Variables

Add these variables to your `.env` file:

```env
# SP-API Credentials
SP_API_REFRESH_TOKEN=Atzr|your_refresh_token_here
SP_API_LWA_APP_ID=amzn1.application-oa2-client.your_app_id_here  
SP_API_LWA_CLIENT_SECRET=your_client_secret_here

# Optional: Marketplace configuration
SP_API_DEFAULT_MARKETPLACE=ATVPDKIKX0DER  # US marketplace
```

## Step 5: Install Dependencies

The SP-API integration requires the `python-amazon-sp-api` package:

```bash
pip install python-amazon-sp-api==0.24.4
```

This is already added to `requirements.txt`.

## Step 6: Test Integration

1. Start your backend server
2. Check logs for SP-API initialization
3. Navigate to the dashboard overview page
4. The system will automatically try SP-API first, then fallback to Sellerboard if needed

## Marketplace IDs

Common marketplace IDs for SP-API:

- **US**: `ATVPDKIKX0DER`
- **Canada**: `A2EUQ1WTGCTBG2`
- **Mexico**: `A1AM78C64UM0Y8`
- **Germany**: `A1PA6795UKMFR9`
- **UK**: `A1F83G8C2ARO7P`
- **France**: `A13V1IB3VIYZZH`
- **Italy**: `APJ6JRA9NG5V4`
- **Spain**: `A1RKKUPIHCS9HS`
- **Japan**: `A1VC38T7YXB528`
- **Australia**: `A39IBJ37TRP1C6`

## Benefits of SP-API vs Sellerboard

✅ **Real-time data** directly from Amazon  
✅ **More accurate** inventory and sales information  
✅ **No third-party dependencies** or costs  
✅ **Better rate limits** and reliability  
✅ **Enhanced data** including order details, catalog info  
✅ **Future-proof** official Amazon API  

## Troubleshooting

### Common Issues

1. **"SP-API client not available"**
   - Check that environment variables are set correctly
   - Verify the `python-amazon-sp-api` package is installed
   - Ensure your refresh token is valid

2. **"Access denied to SP-API"**
   - Verify your seller account has SP-API access
   - Check that your application has the required roles/permissions
   - Confirm marketplace ID matches your seller account region

3. **"Invalid refresh token"**
   - Refresh tokens can expire if not used for 6 months
   - Re-authorize your application to get a new refresh token
   - Check token format (should start with "Atzr|")

### Logs

Monitor backend logs for SP-API activity:
- `[SP-API]` - General SP-API operations
- `[SP-API Analytics]` - Analytics processing
- `[SP-API ERROR]` - Error conditions

### Fallback Behavior

The system is designed to gracefully fallback:
1. **First**: Try SP-API with your credentials
2. **Second**: Fallback to Sellerboard if SP-API fails
3. **Third**: Show error if both fail

This ensures uninterrupted service during the transition.

## Next Steps

Once SP-API is working:
1. You can remove Sellerboard URLs from user settings
2. Consider adding marketplace selection to user profiles
3. Implement additional SP-API endpoints (Reports, Catalog, etc.)
4. Add historical data processing capabilities

## Support

For SP-API specific issues:
- [Amazon SP-API Developer Guide](https://developer-docs.amazon.com/sp-api/docs)
- [SP-API GitHub Issues](https://github.com/python-amazon-sp-api/python-amazon-sp-api/issues)

For integration issues:
- Check backend logs
- Verify environment configuration
- Test with sandbox endpoints first