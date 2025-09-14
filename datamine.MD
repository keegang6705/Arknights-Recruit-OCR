Mining data from https://puppiizsunniiz.github.io/AN-EN-Tags/akhr.html  

https://github.com/copilot/share/8056002e-0044-8cb0-a113-824d0443002e  
```
if (typeof JsonDATA !== "undefined" && JsonDATA.all_chars) {
    const operators = Object.values(JsonDATA.all_chars);

    // Build a list of all English tags for lookup
    const tagDictEN = {};
    if (Array.isArray(JsonDATA.tagsTL)) {
        JsonDATA.tagsTL.forEach(tagObj => {
            tagDictEN[tagObj.tag_en] = tagObj.tag_en;
            tagDictEN[tagObj.tag_cn] = tagObj.tag_en; // Map CN to EN for reverse lookup
        });
    }

    const csvRows = [
        "id,name_en,name_cn,rarity,tags_en"
    ];
    operators.forEach(op => {
        // Map operator tags to English, fallback to tag as-is if not found
        const tagsEN = (op.tags || []).map(tag => tagDictEN[tag] || tag).join(";");
        csvRows.push(`"${op.id}","${op.name_en}","${op.name_cn}",${op.level},"${tagsEN}"`);
    });
    console.log(csvRows.join("\n"));
} else {
    console.log("JsonDATA or all_chars not loaded yet. Please wait for the page to finish loading, then try again.");
}
```
clean data with clean.py  