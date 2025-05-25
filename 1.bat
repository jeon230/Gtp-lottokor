cd /d %~dp0

:: 1. 기존 Git 무시하고 새로 초기화
rmdir /s /q .git
git init

:: 2. 원격 저장소 재등록
git remote add origin https://github.com/jeon230/Gtp-lottokor.git

:: 3. 전체 파일 추가 및 강제 커밋
git add .
git commit -m "🚨 저장소 초기화: 새 프로젝트 전체 업로드"

:: 4. 원격 브랜치 강제 덮어쓰기
git push -f origin main
