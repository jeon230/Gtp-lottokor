@echo off
cd /d %~dp0
git init
git remote add origin https://github.com/jeon230/gtp-lottokor.git
git add .
git commit -m "🚀 초기 커밋: 로또 GPU 추천 시스템 업로드"
git push -u origin main
pause
