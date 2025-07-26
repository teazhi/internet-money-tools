# Amazon Seller Dashboard

A comprehensive web dashboard for the Discord bot that provides Amazon seller management tools including inventory tracking, sales analytics, and automated reporting.

## Features

### 🔐 Authentication
- Discord OAuth integration for secure user authentication
- User-specific dashboards with personalized data
- Session management with secure cookies

### 📊 Dashboard Overview
- Real-time sales analytics and performance metrics
- Top-selling products with velocity tracking
- Stock level monitoring and alerts
- Setup progress tracking

### 📈 Advanced Analytics
- Interactive charts showing sales trends and velocity
- Stock level distribution analysis
- 30-day stockout risk assessment
- Product performance comparisons

### 🔗 Google Sheets Integration
- Step-by-step Google account linking process
- Spreadsheet and worksheet selection
- Intelligent column mapping for data synchronization
- Real-time data fetching with token refresh handling

### ⚙️ User Settings
- Profile management with email configuration
- Listing loader and Sellerboard file configuration
- Script automation toggle
- Account status overview

## Architecture

### Backend (Flask)
- RESTful API with Flask and Flask-CORS
- AWS S3 integration for user configuration storage
- Google Sheets API integration
- Discord OAuth authentication
- Session management

### Frontend (React)
- Modern React application with hooks and context
- Tailwind CSS for responsive styling
- Recharts for data visualization
- React Router for navigation
- Axios for API communication

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- AWS account with S3 bucket
- Discord application with OAuth2 credentials
- Google Cloud project with Sheets API enabled

### Environment Variables
Create a `.env` file in the backend directory:

```env
# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here

# Discord OAuth
DISCORD_CLIENT_ID=your-discord-client-id
DISCORD_CLIENT_SECRET=your-discord-client-secret
DISCORD_REDIRECT_URI=http://localhost:5000/auth/discord/callback

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=your-google-redirect-uri

# AWS Configuration
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
CONFIG_S3_BUCKET=your-s3-bucket-name
```

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd dashboard/backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the Flask application:
   ```bash
   python app.py
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd dashboard/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## API Endpoints

### Authentication
- `GET /auth/discord` - Initiate Discord OAuth flow
- `GET /auth/discord/callback` - Handle Discord OAuth callback
- `GET /auth/logout` - Logout user

### User Management
- `GET /api/user` - Get current user information
- `POST /api/user/profile` - Update user profile

### Google Integration
- `GET /api/google/auth-url` - Get Google OAuth URL
- `POST /api/google/complete-auth` - Complete Google OAuth
- `GET /api/google/spreadsheets` - List user's spreadsheets
- `GET /api/google/worksheets/<id>` - List worksheets in spreadsheet

### Sheet Configuration
- `POST /api/sheet/configure` - Save sheet configuration
- `GET /api/sheet/headers/<id>/<title>` - Get sheet headers

### Analytics
- `GET /api/analytics/orders` - Get orders analytics data

## Components

### Dashboard Components
- **Overview**: Main dashboard with key metrics and alerts
- **Analytics**: Advanced charts and data visualization
- **Settings**: User profile and configuration management
- **SheetConfig**: Step-by-step Google Sheets setup wizard

### Shared Components
- **Login**: Discord OAuth authentication interface
- **ProtectedRoute**: Route protection for authenticated users
- **AuthContext**: Global authentication state management

## Features in Detail

### Setup Wizard
The dashboard includes a comprehensive setup wizard that guides users through:
1. Discord authentication
2. Google account linking
3. Spreadsheet selection
4. Worksheet selection
5. Column mapping
6. Profile configuration

### Real-time Data
- Fetches live data from Google Sheets
- Automatic token refresh for uninterrupted access
- Error handling and retry mechanisms

### Responsive Design
- Mobile-friendly interface
- Adaptive layouts for different screen sizes
- Accessible design patterns

### Security
- Secure session management
- CORS protection
- Input validation and sanitization
- Protected API endpoints

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.