# DEV MODE - Hot reload Angular
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .
EXPOSE 4200

# 🔥 ng serve avec hot-reload
CMD ["ng", "serv"]
