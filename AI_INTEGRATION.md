# AI Analytics Integration

This document describes the AI-powered analytics features integrated into the e-commerce platform using Keywords.ai.

## Overview

The AI integration provides intelligent insights, predictive analytics, and automated recommendations for e-commerce data analysis. It leverages Keywords.ai's LLM monitoring platform to deliver actionable business intelligence.

## Features

### 1. Smart Order Analysis (`/api/analytics/ai-insights`)
- **Automated insights** from sales data patterns
- **Performance summaries** with key metrics analysis  
- **Trend identification** and anomaly detection
- **Contextual explanations** for data changes

### 2. Predictive Restocking (`/api/analytics/restock-ai`)
- **Sales velocity analysis** across products
- **Inventory runout predictions** based on historical data
- **Optimal order quantity recommendations** 
- **Urgency-based prioritization** (critical/high/medium/low)

### 3. Profit Optimization (`/api/analytics/profit-optimization`)
- **Margin analysis** by product and category
- **Pricing opportunity identification**
- **Cost reduction recommendations**
- **Product mix optimization suggestions**

### 4. Enhanced Dashboard Intelligence
- **AI-powered summaries** integrated into existing analytics
- **Top insights** and recommendations displayed automatically
- **Natural language explanations** of performance metrics

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements-ai.txt
```

### 2. Get Keywords.ai API Key
1. Sign up at [keywordsai.co](https://keywordsai.co)
2. Generate an API key from your dashboard
3. Add to your environment variables

### 3. Environment Configuration
```bash
# Add to your .env file
KEYWORDS_AI_API_KEY=your-keywords-ai-api-key-here
```

### 4. Verify Installation
The AI features will automatically detect if Keywords.ai is configured:
- ✅ Enabled: Full AI insights and recommendations
- ❌ Disabled: Graceful fallback with informational messages

## API Endpoints

### AI Insights
```http
GET /api/analytics/ai-insights?date=2024-01-15
```

**Response:**
```json
{
  "insights": [
    "Your best-selling product achieved 15% higher margins this week",
    "Sales velocity increased 23% compared to last month"
  ],
  "recommendations": [
    "Consider increasing inventory for ASIN B08XYZ123 based on high demand",
    "Optimize pricing for underperforming products with <20% margins"
  ],
  "warnings": ["Declining sales detected for 3 products"],
  "opportunities": ["Bundle opportunities identified for complementary products"],
  "date": "2024-01-15",
  "total_orders": 45,
  "ai_enabled": true
}
```

### Predictive Restocking
```http
GET /api/analytics/restock-ai
```

**Response:**
```json
{
  "recommendations": [
    {
      "asin": "B08XYZ123",
      "product_name": "Wireless Headphones",
      "recommended_order_quantity": 50,
      "urgency": "high",
      "reasoning": "Current velocity of 2.5 units/day will exhaust stock in 12 days",
      "estimated_runout_days": 12
    }
  ],
  "lead_time_days": 90,
  "analysis_period": "2024-01-01 to 2024-01-30",
  "ai_enabled": true
}
```

### Profit Optimization
```http
GET /api/analytics/profit-optimization
```

**Response:**
```json
{
  "opportunities": [
    {
      "type": "pricing",
      "description": "Increase price by 8% for high-demand, low-margin products",
      "potential_impact": "$2,450 additional monthly profit"
    },
    {
      "type": "cost_reduction", 
      "description": "Negotiate better rates with suppliers for top 5 products",
      "potential_impact": "15% margin improvement"
    }
  ],
  "analysis_period": "2024-01-08 to 2024-01-15",
  "ai_enabled": true
}
```

## Frontend Integration

### Dashboard Integration
AI insights are automatically included in the main analytics response:

```javascript
// Analytics data now includes AI insights
const analyticsData = await fetch('/api/analytics/orders');
const aiInsights = analyticsData.ai_insights;

if (aiInsights.enabled) {
  // Display AI summaries
  console.log(aiInsights.summary); // Top 3 insights
  console.log(aiInsights.top_recommendation); // Primary recommendation
}
```

### Dedicated AI Components
Use the `AIInsights` component for dedicated AI analysis:

```jsx
import AIInsights from './components/AIInsights';

function Dashboard() {
  return (
    <div>
      {/* Existing analytics components */}
      <AIInsights 
        selectedDate={selectedDate}
        analyticsData={analyticsData}
      />
    </div>
  );
}
```

## Technical Architecture

### AI Analytics Module (`ai_analytics.py`)
- **Keywords.ai Integration**: Unified LLM API with monitoring
- **Data Processing**: Pandas-based analysis and preparation
- **Insight Generation**: Structured prompts for business intelligence
- **Error Handling**: Graceful fallbacks when AI is unavailable

### Integration Points
1. **Order Analysis Pipeline**: Enhanced with AI insights
2. **Caching System**: AI results cached with analytics data
3. **User Configuration**: Respects existing user settings and permissions
4. **Error Boundaries**: AI failures don't break core functionality

## Performance Considerations

### Monitoring with Keywords.ai
- **Request Tracking**: All AI calls monitored for performance
- **Cost Management**: Token usage and API costs tracked
- **A/B Testing**: Compare AI vs non-AI user experiences
- **Analytics**: Monitor which insights drive user actions

### Optimization Strategies
- **Intelligent Caching**: AI insights cached with analytics data
- **Batch Processing**: Multiple dates analyzed together when possible
- **Progressive Enhancement**: Core features work without AI
- **Rate Limiting**: Prevent excessive AI API usage

## Cost Management

### Keywords.ai Benefits
- **Unified Pricing**: Single platform for multiple LLM providers
- **Cost Monitoring**: Built-in usage tracking and alerts
- **Optimization Tools**: Automatic model selection for cost efficiency

### Usage Patterns
- **Dashboard Views**: Light AI summaries (2-3 insights)
- **Detailed Analysis**: Full AI insights on-demand
- **Batch Analysis**: Historical data processed efficiently
- **Smart Caching**: Reduce redundant AI calls

## Customization

### Prompt Engineering
Modify prompts in `ai_analytics.py` for different business contexts:

```python
# Customize insights for your business model
prompt = f"""
Analyze this e-commerce data for a {business_type} seller:
Focus on {key_metrics} and provide insights about {priority_areas}
"""
```

### Model Selection
Configure different LLM models via Keywords.ai:

```python
# Use different models for different tasks
response = self.client.generate(
    messages=[{"role": "user", "content": prompt}],
    model="gpt-4-turbo-preview",  # High accuracy for complex analysis
    # model="gpt-3.5-turbo",      # Cost-effective for simple insights
    temperature=0.7
)
```

## Troubleshooting

### Common Issues

1. **AI Not Working**
   - Check `KEYWORDS_AI_API_KEY` environment variable
   - Verify Keywords.ai account status and credits
   - Check application logs for API errors

2. **Slow Performance**
   - Review Keywords.ai dashboard for latency metrics
   - Consider caching strategies for frequently accessed data
   - Use lighter models for real-time features

3. **Inconsistent Insights**
   - Increase data quality by ensuring clean order data
   - Adjust prompt temperature for more/less creative responses
   - Review and refine prompt engineering

### Debug Mode
Enable detailed logging:

```python
# Add to ai_analytics.py for debugging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Natural Language Queries**: Ask questions about your data
- **Automated Reports**: Weekly/monthly AI-generated summaries
- **Seasonal Predictions**: Holiday and trend-based forecasting
- **Competitive Analysis**: Market positioning recommendations

### Integration Opportunities
- **Email Alerts**: AI-powered anomaly notifications
- **Slack/Discord**: Automated insight delivery
- **Mobile Apps**: Push notifications for critical insights
- **Webhooks**: Real-time AI insights for external systems

## Support

For technical support:
1. Check Keywords.ai documentation and status page
2. Review application logs for specific error messages
3. Verify data quality and format requirements
4. Contact support with specific error details and use cases