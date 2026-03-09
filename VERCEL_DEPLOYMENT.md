# Vercel Deployment Guide

## Prerequisites
- Vercel account (sign up at [vercel.com](https://vercel.com))
- Git repository (GitHub, GitLab, or Bitbucket)
- Vercel CLI installed (optional): `npm i -g vercel`

## Quick Deploy (Recommended)

### Option 1: Deploy via Vercel Dashboard
1. Push your code to GitHub/GitLab/Bitbucket
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your repository
4. Vercel will auto-detect the Python project
5. Configure environment variables (see below)
6. Click **Deploy**

### Option 2: Deploy via CLI
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy (from project root)
vercel

# Deploy to production
vercel --prod
```

## Environment Variables

Add these in Vercel Dashboard (Settings → Environment Variables):

### Required:
- `OPENAI_API_KEY` - Your OpenAI API key
- `INTERNAL_API_KEY` - Your internal API key

### Optional:
- `MAPBOX_API_KEY` - For location services
- `NODEJS_BACKEND_URL` - Your Node.js backend URL
- `TWILIO_ACCOUNT_SID` - Twilio account SID
- `TWILIO_AUTH_TOKEN` - Twilio auth token
- `TWILIO_PHONE_NUMBER` - Twilio phone number
- `OWNER_PHONE_NUMBER` - Notification phone number

## Important Notes

### ⚠️ Timeout Limitations
- **Hobby Plan**: 10 second timeout per request
- **Pro Plan**: 60 second timeout per request
- If OpenAI responses take longer, requests will fail

### Cold Starts
- First request after idle: 1-3 seconds delay
- Frequent for low-traffic apps
- No way to keep function "warm" on Hobby plan

### Cost
- **Hobby**: Free (limit: 100GB bandwidth/month)
- **Pro**: $20/month (1TB bandwidth, 60s timeout)

## Verifying Deployment

After deployment, test your endpoints:

```bash
# Health check
curl https://your-app.vercel.app/health

# Root endpoint
curl https://your-app.vercel.app/

# API status
curl https://your-app.vercel.app/api/status
```

## Monitoring

View logs in Vercel Dashboard:
1. Go to your project
2. Click **Deployments**
3. Click on a deployment
4. View **Functions** logs

## Troubleshooting

### Issue: 504 Gateway Timeout
**Solution**: 
- Upgrade to Pro plan for 60s timeout
- Optimize OpenAI calls
- Consider switching to Render/Railway for no timeout

### Issue: Cold starts are slow
**Solution**:
- Expected behavior on serverless
- Consider Render with always-on instances

### Issue: Environment variables not working
**Solution**:
- Redeploy after adding env vars
- Check variable names match exactly
- Verify in Settings → Environment Variables

## Comparing with Render

| Feature | Vercel Hobby | Vercel Pro | Render Free | Render Paid |
|---------|--------------|------------|-------------|-------------|
| **Price** | Free | $20/mo | Free | $7/mo |
| **Timeout** | 10s | 60s | None | None |
| **Cold Start** | 1-3s | 1-3s | 30-60s | None |
| **Always On** | No | No | No | Yes |
| **Best For** | Quick APIs | Fast APIs | Testing | AI/ML Apps |

## Recommendation

- **For testing**: Start with Vercel Hobby
- **For production AI apps**: Use Render Paid ($7/mo) or Vercel Pro ($20/mo)
- **Best value**: Render Paid (no timeout, always-on, cheaper)

## Rollback to Render

If Vercel doesn't work well, you can always:
1. Use your existing `render.yaml` configuration
2. Deploy to Render.com
3. Keep both deployments (test on Vercel, production on Render)

## Support

- Vercel Docs: https://vercel.com/docs
- Vercel Discord: https://vercel.com/discord
