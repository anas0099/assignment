BING_HTML_WITH_ADS = """
<!DOCTYPE html>
<html>
<head><title>python - Bing</title></head>
<body>
<ol id="b_results">
    <li class="b_ad">
        <div class="sb_add">
            <a href="https://ad1.example.com">Ad 1</a>
            <a href="https://ad1-link2.example.com">Ad 1 link</a>
        </div>
    </li>
    <li class="b_ad b_adTop">
        <div class="sb_add">
            <a href="https://ad2.example.com">Ad 2</a>
        </div>
    </li>
    <li class="b_algo">
        <h2><a href="https://python.org">Python.org</a></h2>
        <p>Welcome to Python</p>
    </li>
    <li class="b_algo">
        <h2><a href="https://docs.python.org">Python Docs</a></h2>
        <p>Documentation</p>
    </li>
    <li class="b_algo">
        <h2><a href="https://pypi.org">PyPI</a></h2>
    </li>
    <li class="b_ad b_adBottom b_adLastChild">
        <div class="sb_add">
            <a href="https://ad3.example.com">Ad 3</a>
        </div>
    </li>
</ol>
</body>
</html>
"""

BING_HTML_NO_ADS = """
<!DOCTYPE html>
<html>
<head><title>obscure term - Bing</title></head>
<body>
<ol id="b_results">
    <li class="b_algo">
        <h2><a href="https://example.com/result1">Result 1</a></h2>
    </li>
    <li class="b_algo">
        <h2><a href="https://example.com/result2">Result 2</a></h2>
    </li>
    <li class="b_algo">
        <h2><a href="https://example.com/result3">Result 3</a></h2>
    </li>
</ol>
</body>
</html>
"""
