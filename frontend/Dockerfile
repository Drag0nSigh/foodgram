FROM node:21.7.1-alpine
WORKDIR /app
COPY package.json package.json
COPY package-lock.json package-lock.json
RUN npm ci --legacy-peer-deps
COPY . ./
RUN npm run build
