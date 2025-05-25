#!/bin/bash
cd $(dirname $0)
git init
git remote add origin https://github.com/jeon230/Gtp-lottokor.git
git add .
git commit -m "🚀 초기 커밋: 로또 GPU 추천 시스템 업로드"
git push -u origin main
