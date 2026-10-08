"""Pinned authored C# plus a closed token allowlist for observed native wrappers.

Source compatibility only: this does not attest the loaded compiled assembly.
"""
from hashlib import sha256
import re

from backend.market_data.analysis_time_profile_v1 import require

BOUNDARY = '#region NinjaScript generated code. Neither change nor remove.'
AUTHORED_SHA256 = '5542b9b5ae859af42ad376e04b2ac68c300bf22a246f9efe0948a6512c75e12b'
WRAPPER_TOKENS_SHA256 = '2486b08e800547e39c02fa8da0aa59637b9408eca89ff69c35f1e3fa5b4d05c3'


def verify_exporter_source(source):
    # Decode exactly once. Only UTF-8 BOM, CRLF and separating blank LF lines
    # are normalized. No whitespace/comment/runtime-code stripping in the body.
    text = source.decode('utf-8-sig').replace('\r\n', '\n')
    require('\r' not in text and '\x00' not in text, 'INSTALLED_EXPORTER_MISMATCH')
    count = text.count(BOUNDARY)
    require(count <= 1, 'AMBIGUOUS_GENERATED_BOUNDARY')
    authored = text
    if count:
        authored, tail = text.split(BOUNDARY)
        require(authored.endswith('\n') and tail.startswith('\n'), 'MALFORMED_GENERATED_BOUNDARY')
        require(tail.count('#endregion') == 1 and tail.rstrip('\n').endswith('#endregion'),
                'MALFORMED_GENERATED_TAIL')
        # Pin the entire generated tail, including its terminal #endregion.
        # Lexical tokens, not whitespace removal: split identifiers/operators
        # cannot alias legal tokens. No comments/directives/literals are allowed.
        tokens = re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+|==|!=|\+\+|\S', tail)
        require(sha256('\n'.join(tokens).encode()).hexdigest() == WRAPPER_TOKENS_SHA256,
                'UNRECOGNIZED_GENERATED_TAIL')
    digest = sha256(authored.rstrip('\n').encode('utf-8')).hexdigest()
    require(digest == AUTHORED_SHA256, 'INSTALLED_EXPORTER_MISMATCH')
    return dict(authored_sha256=digest, generated_tail='VERIFIED_TOKENS' if count else 'ABSENT',
                compiled_assembly_attested=False)
