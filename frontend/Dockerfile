FROM node:20 AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

ARG VITE_SHOW_SAJU_LINK=false
ARG VITE_SAJU_SERVICE_URL=

ENV VITE_SHOW_SAJU_LINK=$VITE_SHOW_SAJU_LINK
ENV VITE_SAJU_SERVICE_URL=$VITE_SAJU_SERVICE_URL

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
