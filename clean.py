replacing ={"近卫": "Guard",
             "狙击": "Sniper", 
             "重装": "Defender",
             "医疗": "Medic",
             "辅助": "Supporter",
             "术师": "Caster",
             "特种": "Specialist",
             "先锋": "Vanguard",
             "女": "Female",
             "男": "Male",
             '""':'"'}

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with open("./data/operatordata.csv", "r", encoding="utf-8") as f:
    data = f.read()

for key, value in replacing.items():
    data = data.replace(key, value)

with open("./data/operatordata_en.csv", "w", encoding="utf-8") as f:
    f.write(data)

print("Replacement complete. New file saved as operatordata_en.csv")