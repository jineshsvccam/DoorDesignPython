import pandas as pd

# Load the Excel file
df = pd.read_excel("_Single_Door_Duct_Door🚪__2025-2026_1758777986959.xlsx", sheet_name=0)

# Clean column names
df.columns = df.columns.str.strip()

# Rename columns for clarity
df = df.rename(columns={
    df.columns[0]: 'Door Name',
    df.columns[1]: 'Dimension Type',  # Width or Height
    df.columns[2]: 'Frame Size',
    df.columns[3]: 'Left Side 25mm',
    df.columns[4]: 'Right Side 25mm',
    df.columns[5]: 'Total Frame',
    df.columns[6]: 'Minus',
    df.columns[7]: 'Opening',
    df.columns[8]: 'Bending',
    df.columns[9]: 'Cutting'
})

# Fill missing door names
df['Door Name'] = df['Door Name'].ffill()

# Split into Width and Height rows
width_df = df[df['Dimension Type'].str.lower() == 'width']
height_df = df[df['Dimension Type'].str.lower() == 'height']

# Merge Width and Height rows
merged = pd.merge(width_df, height_df, on='Door Name', suffixes=('_Width', '_Height'))

# Select and rename final columns
final = merged[[
    'Door Name',
    'Frame Size_Width', 'Frame Size_Height',
    'Left Side 25mm_Width', 'Left Side 25mm_Height',
    'Right Side 25mm_Width', 'Right Side 25mm_Height',
    'Total Frame_Width', 'Total Frame_Height',
    'Minus_Width', 'Minus_Height',
    'Opening_Width', 'Opening_Height',
    'Bending_Width', 'Bending_Height',
    'Cutting_Width', 'Cutting_Height'
]].rename(columns={
    'Frame Size_Width': 'Frame Width',
    'Frame Size_Height': 'Frame Height',
    'Left Side 25mm_Width': 'Left Margin Width',
    'Left Side 25mm_Height': 'Left Margin Height',
    'Right Side 25mm_Width': 'Right Margin Width',
    'Right Side 25mm_Height': 'Right Margin Height',
    'Total Frame_Width': 'Total Frame Width',
    'Total Frame_Height': 'Total Frame Height',
    'Minus_Width': 'Minus Width',
    'Minus_Height': 'Minus Height',
    'Opening_Width': 'Opening Width',
    'Opening_Height': 'Opening Height',
    'Bending_Width': 'Bending Width',
    'Bending_Height': 'Bending Height',
    'Cutting_Width': 'Cutting Width',
    'Cutting_Height': 'Cutting Height'
})

# Save to new Excel file
final.to_excel("Restructured_Door_Measurements.xlsx", index=False)