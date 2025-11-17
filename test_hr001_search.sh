#!/bin/bash

# HR001 사용자 토큰
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJIUjAwMSIsInVzZXJfaWQiOjUwLCJ1c2VybmFtZSI6ImhyLm1hbmFnZXIiLCJpc19hZG1pbiI6ZmFsc2UsImV4cCI6MTc1NDI5OTU1MH0.VyeTOLH3Ome_uGbx78n-iLLgTjTsy3Xgvl4oFQrzOUQ"

echo "=== HR001 사용자로 검색 API 테스트 ==="
echo "검색어: 로봇"
echo ""

# 검색 API 호출
curl -X 'POST' \
  'http://localhost:8000/api/v1/search/hybrid' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer '$TOKEN \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "로봇",
  "max_results": 5
}' | python3 -m json.tool

echo ""
echo "=== 두 번째 테스트: ERP 검색 ==="
echo ""

curl -X 'POST' \
  'http://localhost:8000/api/v1/search/hybrid' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer '$TOKEN \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "ERP",
  "max_results": 5
}' | python3 -m json.tool
