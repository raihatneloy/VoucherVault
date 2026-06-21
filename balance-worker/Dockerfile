FROM node:22-bookworm-slim

# Install system dependencies for Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files and install Node deps
COPY package.json ./
RUN npm install --omit=dev && \
    rm -rf /root/.npm

# Install Playwright's Chromium (headless shell, ~120MB)
RUN npx playwright install chromium-headless-shell && \
    rm -rf /tmp/*

# Set Playwright browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Copy app source
COPY server.js balance.js ./

EXPOSE 3001
CMD ["node", "server.js"]
