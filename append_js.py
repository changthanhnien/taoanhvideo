import os
path = r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\features\watermark_remove\source\static\main.js'
with open(path, 'a', encoding='utf-8') as f:
    f.write('\n\ndocument.addEventListener("DOMContentLoaded", function() {\n')
    f.write('    const btnDownloadAll = document.getElementById("btn-download-all");\n')
    f.write('    if (btnDownloadAll) {\n')
    f.write('        btnDownloadAll.addEventListener("click", function(e) {\n')
    f.write('            e.preventDefault();\n')
    f.write('            window.location.href = "/api/download_all";\n')
    f.write('        });\n')
    f.write('    }\n')
    f.write('});\n')
print("Appended JS logic")
