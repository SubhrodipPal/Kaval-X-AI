import sys
import json

source_file = r'C:\Users\Subhrodip\.gemini\antigravity\brain\f5c5c0d1-a586-4d6e-95e7-7186798895ca\.system_generated\steps\3\content.md'
output_file = r'd:\Kavalx_AI\blueprint_source.jsx'

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the JSX source - it starts with 'import { useState }'
marker = 'import { useState } from'
start = content.find(marker)
if start == -1:
    print('JSX source not found')
    sys.exit(1)

# The JSX ends at the next script tag boundary
# Look for the pattern that ends the push: "])</script>"
# Actually the content is JSON-escaped inside self.__next_f.push([1,"..."])
# We need to find the end of this push block

# The source code block starts after '10:Teec6,"' and is in the next push
# Let's collect all the push contents after our start position
# Find where this particular push's string content ends
# In the HTML, pushes are: self.__next_f.push([1,"CONTENT"])
# But content might span multiple pushes

# Let's find the full JSX by looking for the export default
jsx_content = content[start:]

# The JSX is JSON-escaped, find where it transitions back to HTML/script tags
# Look for the closing pattern
end_markers = ['"])</script>', '\\"])</script>']
end_pos = len(jsx_content)
for marker in end_markers:
    pos = jsx_content.find(marker)
    if pos != -1 and pos < end_pos:
        end_pos = pos

jsx_content = jsx_content[:end_pos]

# Unescape JSON string
jsx_content = jsx_content.replace('\\n', '\n')
jsx_content = jsx_content.replace('\\"', '"')
jsx_content = jsx_content.replace('\\t', '\t')
jsx_content = jsx_content.replace('\\\\', '\\')
jsx_content = jsx_content.replace('\\u003c', '<')
jsx_content = jsx_content.replace('\\u003e', '>')
jsx_content = jsx_content.replace('\\u0026', '&')

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(jsx_content)

lines = jsx_content.count('\n')
print(f'Extracted {len(jsx_content)} chars, {lines} lines')
