FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

ENV VITE_API_URL=http://api:8000

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
