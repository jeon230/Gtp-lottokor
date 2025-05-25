# GPU 기반 추천 시스템 - 최종 시각화 버전
import cupy as cp
import itertools
import pandas as pd
from collections import Counter
import os
import datetime
import numpy as np
from jinja2 import Template
import pdfkit
import json

# 설정 로딩
with open("../data/lotto_config.json", "r", encoding="utf-8-sig") as f:
    config = json.load(f)

filters = config["filters"]
scoring = config["scoring"]
selection = config["selection"]
paths = config["data_paths"]
visual = config["visualization"]

print("📁 [1/10] 저장 디렉토리 생성 완료")
df = pd.read_excel(paths["lotto_excel"])
df = df.dropna(subset=[f"번호{i}" for i in range(1, 7)])
df_sorted = df.sort_values("회차", ascending=False).reset_index(drop=True)

print("🚫 [2/10] 제외노머 로드 완료")
recent_15 = df_sorted.head(15)[[f"번호{i}" for i in range(1, 7)]].astype(int).values.flatten()
recent_20 = df_sorted.head(20)[[f"번호{i}" for i in range(1, 7)]].astype(int).values.flatten()
recent_50 = df_sorted.head(50)[[f"번호{i}" for i in range(1, 7)]].astype(int).values
last_winner = df_sorted.iloc[0][[f"번호{i}" for i in range(1, 7)]].astype(int).tolist()

cnt_15 = Counter(recent_15)
cnt_20 = Counter(recent_20)
all_numbers = set(range(1, 46))
non_appeared_15 = sorted(all_numbers - set(cnt_15.keys()))
freq_20 = [cnt_20.get(n, 0) for n in range(1, 46)]

print("📊 [3/10] 로또 전체 데이터 로드 완료")
sum_range_min, sum_range_max = scoring["use_total_sum_range"]
print("📈 [4/10] 전체 통계 계산 완료")

combos = cp.array(list(itertools.combinations(range(1, 46), 6)), dtype=cp.int16)
combos = cp.sort(combos, axis=1)

mask = cp.ones(combos.shape[0], dtype=cp.bool_)
if filters["consecutive_count_limit"] < 6:
    diff = cp.diff(combos, axis=1)
    consec = cp.zeros_like(diff[:, 0])
    max_run = cp.zeros_like(diff[:, 0])
    for i in range(diff.shape[1]):
        consec = cp.where(diff[:, i] == 1, consec + 1, 0)
        max_run = cp.maximum(max_run, consec)
    mask &= max_run < (filters["consecutive_count_limit"] - 1)

if filters["all_even_or_all_odd"]:
    even_count = cp.sum(combos % 2 == 0, axis=1)
    mask &= (even_count != 0) & (even_count != 6)

recent50_set = [set(row) for row in recent_50.tolist()]
combo_sets = [set(row.tolist()) for row in combos.get()]
overlap_mask = cp.array([
    all(len(c & s) < filters["recent_overlap_limit"] for s in recent50_set) for c in combo_sets
], dtype=cp.bool_)
mask &= overlap_mask

last_win_set = set(last_winner)
last_overlap_mask = cp.array([
    len(set(row.tolist()) & last_win_set) < filters["last_winner_overlap_limit"]
    for row in combos.get()
], dtype=cp.bool_)
mask &= last_overlap_mask

valid_combos = combos[mask]
print(f"✅ [5/10] GPU 전체 필터링 완료 → 유효 조합 수: {valid_combos.shape[0]:,}")
print("📤 [6/10] 결과 CPU 전송 완료")

non_appeared_arr = cp.array(non_appeared_15, dtype=cp.int16)
freq_arr = cp.array(freq_20, dtype=cp.int16)
base_score = freq_arr[valid_combos - 1].sum(axis=1) if scoring["use_recent_frequency_20"] else 0
bonus_score = cp.isin(valid_combos, non_appeared_arr).sum(axis=1) * scoring["non_appeared_bonus"]
sums = cp.sum(valid_combos, axis=1)
sum_bonus = cp.where((sums >= sum_range_min) & (sums <= sum_range_max), scoring["sum_range_bonus"], 0)

if scoring.get("use_marking_heatmap", False):
    heatmap = np.load(paths["marking_heatmap_path"])
    heatmap_cp = cp.asarray(heatmap.astype(cp.float32))
    mark_score = heatmap_cp[valid_combos - 1].sum(axis=1) * scoring["marking_bonus"]
else:
    mark_score = 0

total_score = base_score + bonus_score + sum_bonus + mark_score

sorted_idx = cp.argsort(-total_score)
selected_pool = valid_combos[sorted_idx[:selection["top_n"]]]
final_indices = cp.random.choice(selection["top_n"], selection["random_pick"], replace=False)
final_selection = selected_pool[final_indices]

now = datetime.datetime.now().strftime("%m%d-%H-%M")
save_dir = os.path.join(paths["save_dir"], now)
os.makedirs(save_dir, exist_ok=True)

with open(os.path.join(save_dir, "추천_번호결과.txt"), "w", encoding="utf-8") as f:
    for i, row in enumerate(final_selection.get()):
        f.write(f"{i+1:02d}: {' '.join(f'{x:02d}' for x in row)}\n")
print("📅 [7/10] 추천 결과 텍스트 저장 완료")

# HTML 시각화 템플릿 적용 (로또 용지 스타일)
if visual["enable_html"]:
    template_path = "../data/lotto_ticket_template_horizontal_dynamic_watermark_tiled.html"
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())
    latest_round = int(df_sorted["회차"].iloc[0])
    html_rendered = template.render(data=final_selection.get(), next_round=latest_round + 1)
    html_path = os.path.join(save_dir, "추천_번호결과.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_rendered)
    print("🖼️ [8/10] HTML 시각화 저장 완료")

if visual["enable_pdf"]:
    pdf_path = os.path.join(save_dir, "추천_번호결과.pdf")
    pdfkit.from_file(html_path, pdf_path,
                     options={"page-size": "A4", "encoding": "UTF-8", "orientation": "Landscape"},
                     configuration=pdfkit.configuration(wkhtmltopdf=visual["pdf_wkhtmltopdf_path"]))
    print(f"📄 [9/10] PDF 저장 완료 → {pdf_path}")

with open(os.path.join(save_dir, "디버그_로그.txt"), "w", encoding="utf-8") as f:
    f.write(f"전체 조합 수: {combos.shape[0]:,}\n")
    f.write(f"유효 조합 수: {valid_combos.shape[0]:,}\n")
    f.write(f"총합 범위: {sum_range_min}~{sum_range_max}\n")
    f.write(f"미출현 번호: {non_appeared_15}\n")
    f.write(f"직전 1등 번호: {last_winner}\n")
print("🗂️ [10/10] 디버그 로그 저장 완료")
print("✅ 전체 통합 추천 프로세스 완료")
