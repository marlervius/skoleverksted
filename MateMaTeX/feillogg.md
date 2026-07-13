f8ff402
fix: import Semaphore from threading instead of concurrent.futures concurrent.futures does not export Semaphore in Python 3.12. Use threading.Semaphore instead. Co-authored-by: Cursor <cursoragent@cursor.com>

Rollback

All logs
Search
Search

Live tail



#10 8.692 Downloading distro-1.9.0-py3-none-any.whl (20 kB)
#10 8.696 Downloading docstring_parser-0.17.0-py3-none-any.whl (36 kB)
#10 8.705 Downloading google_auth-2.48.0-py3-none-any.whl (236 kB)
#10 8.717 Downloading jiter-0.13.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (360 kB)
#10 8.723 Downloading jsonpointer-3.0.0-py2.py3-none-any.whl (7.6 kB)
#10 8.732 Downloading orjson-3.11.7-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (133 kB)
#10 8.739 Downloading ormsgpack-1.12.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (212 kB)
#10 8.750 Downloading regex-2026.1.15-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (803 kB)
#10 8.755    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 803.6/803.6 kB 245.7 MB/s eta 0:00:00
#10 8.758 Downloading requests-2.32.5-py3-none-any.whl (64 kB)
#10 8.762 Downloading requests_toolbelt-1.0.0-py2.py3-none-any.whl (54 kB)
#10 8.765 Downloading six-1.17.0-py2.py3-none-any.whl (11 kB)
#10 8.769 Downloading tqdm-4.67.3-py3-none-any.whl (78 kB)
#10 8.781 Downloading zstandard-0.25.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (5.5 MB)
#10 8.815    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.5/5.5 MB 171.3 MB/s eta 0:00:00
#10 8.819 Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
#10 8.823 Downloading charset_normalizer-3.4.4-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (153 kB)
#10 8.828 Downloading pyasn1_modules-0.4.2-py3-none-any.whl (181 kB)
#10 8.831 Downloading urllib3-2.6.3-py3-none-any.whl (131 kB)
#10 8.835 Downloading pycparser-3.0-py3-none-any.whl (48 kB)
#10 9.130 Installing collected packages: mpmath, filetype, zstandard, xxhash, XlsxWriter, websockets, uvloop, uuid-utils, urllib3, typing-extensions, tqdm, tenacity, sympy, structlog, sniffio, six, regex, qrcode, pyyaml, python-dotenv, pygments, pycparser, pyasn1, pluggy, Pillow, packaging, ormsgpack, orjson, lxml, jsonpointer, jiter, iniconfig, idna, httptools, h11, docstring-parser, distro, click, charset_normalizer, certifi, asyncpg, annotated-types, annotated-doc, uvicorn, typing-inspection, rsa, requests, python-pptx, python-docx, pytest, pydantic-core, pyasn1-modules, jsonpatch, httpcore, ecdsa, cffi, anyio, watchfiles, tiktoken, starlette, requests-toolbelt, python-jose, pytest-asyncio, pydantic, httpx, cryptography, sse-starlette, pydantic-settings, openai, langsmith, langgraph-sdk, google-auth, fastapi, anthropic, langchain-core, langgraph-checkpoint, langchain-openai, langchain-anthropic, google-genai, langgraph-prebuilt, langchain-google-genai, langgraph
#10 52.69 Successfully installed Pillow-12.1.1 XlsxWriter-3.2.9 annotated-doc-0.0.4 annotated-types-0.7.0 anthropic-0.79.0 anyio-4.12.1 asyncpg-0.31.0 certifi-2026.1.4 cffi-2.0.0 charset_normalizer-3.4.4 click-8.3.1 cryptography-46.0.5 distro-1.9.0 docstring-parser-0.17.0 ecdsa-0.19.1 fastapi-0.129.0 filetype-1.2.0 google-auth-2.48.0 google-genai-1.63.0 h11-0.16.0 httpcore-1.0.9 httptools-0.7.1 httpx-0.28.1 idna-3.11 iniconfig-2.3.0 jiter-0.13.0 jsonpatch-1.33 jsonpointer-3.0.0 langchain-anthropic-1.3.3 langchain-core-1.2.12 langchain-google-genai-4.2.0 langchain-openai-1.1.9 langgraph-1.0.8 langgraph-checkpoint-4.0.0 langgraph-prebuilt-1.0.7 langgraph-sdk-0.3.5 langsmith-0.7.3 lxml-6.0.2 mpmath-1.3.0 openai-2.21.0 orjson-3.11.7 ormsgpack-1.12.2 packaging-26.0 pluggy-1.6.0 pyasn1-0.6.2 pyasn1-modules-0.4.2 pycparser-3.0 pydantic-2.12.5 pydantic-core-2.41.5 pydantic-settings-2.12.0 pygments-2.19.2 pytest-9.0.2 pytest-asyncio-1.3.0 python-docx-1.2.0 python-dotenv-1.2.1 python-jose-3.5.0 python-pptx-1.0.2 pyyaml-6.0.3 qrcode-8.2 regex-2026.1.15 requests-2.32.5 requests-toolbelt-1.0.0 rsa-4.9.1 six-1.17.0 sniffio-1.3.1 sse-starlette-3.2.0 starlette-0.52.1 structlog-25.5.0 sympy-1.14.0 tenacity-9.1.4 tiktoken-0.12.0 tqdm-4.67.3 typing-extensions-4.15.0 typing-inspection-0.4.2 urllib3-2.6.3 uuid-utils-0.14.0 uvicorn-0.40.0 uvloop-0.22.1 watchfiles-1.1.1 websockets-15.0.1 xxhash-3.6.0 zstandard-0.25.0
#10 52.69 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
#10 52.75 
#10 52.75 [notice] A new release of pip is available: 25.0.1 -> 26.0.1
#10 52.75 [notice] To update, run: pip install --upgrade pip
#10 DONE 112.6s
#11 [app 1/1] COPY . .
#11 DONE 0.2s
#12 exporting to docker image format
#12 exporting layers
#12 exporting layers 81.6s done
#12 exporting manifest sha256:53f1dffd86f860973d27a8663a214584131da6bf34fb2afcfe7c0ac75acd5ca6 0.0s done
#12 exporting config sha256:68bdd35c0e06335aa20e23c77c3aad1025445835485a4e31e4217a328ef04942 0.0s done
#12 DONE 91.7s
#13 exporting cache to client directory
#13 preparing build cache for export
#13 writing cache image manifest sha256:3076b779fbd4f1f974ad6d06421a24a07833509c3550c51fda715535d6e01841 0.0s done
#13 DONE 26.8s
Pushing image to registry...
Upload succeeded
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> No open ports detected, continuing to scan...
==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
INFO:     Started server process [7]
INFO:     Waiting for application startup.
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/starlette/routing.py", line 694, in lifespan
    async with self.lifespan_context(app) as maybe_state:
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 226, in __aenter__
    await self._router._startup()
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 4554, in _startup
    await handler()
  File "/app/app/main.py", line 79, in startup
    await get_pool()
  File "/app/app/db.py", line 34, in get_pool
    _pool = await asyncpg.create_pool(
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 439, in _async__init__
    await self._initialize()
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 466, in _initialize
    await first_ch.connect()
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 153, in connect
    self._con = await self._pool._get_new_connection()
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 538, in _get_new_connection
    con = await self._connect(
          ^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connection.py", line 2443, in connect
    return await connect_utils._connect(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 1209, in _connect
    addrs, params, config = _parse_connect_arguments(**kwargs)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 893, in _parse_connect_arguments
    addrs, params = _parse_connect_dsn_and_args(
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 289, in _parse_connect_dsn_and_args
    parsed = urllib.parse.urlparse(dsn)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/urllib/parse.py", line 395, in urlparse
    splitresult = urlsplit(url, scheme, allow_fragments)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/urllib/parse.py", line 514, in urlsplit
    raise ValueError("Invalid IPv6 URL")
ValueError: Invalid IPv6 URL
ERROR:    Application startup failed. Exiting.
==> Exited with status 3
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
INFO:     Started server process [7]
INFO:     Waiting for application startup.
ERROR:    Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/starlette/routing.py", line 694, in lifespan
    async with self.lifespan_context(app) as maybe_state:
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 201, in merged_lifespan
    async with original_context(app) as maybe_original_state:
               ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 226, in __aenter__
    await self._router._startup()
  File "/usr/local/lib/python3.12/site-packages/fastapi/routing.py", line 4554, in _startup
    await handler()
  File "/app/app/main.py", line 79, in startup
    await get_pool()
  File "/app/app/db.py", line 34, in get_pool
    _pool = await asyncpg.create_pool(
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 439, in _async__init__
    await self._initialize()
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 466, in _initialize
    await first_ch.connect()
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 153, in connect
    self._con = await self._pool._get_new_connection()
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/pool.py", line 538, in _get_new_connection
    con = await self._connect(
          ^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connection.py", line 2443, in connect
    return await connect_utils._connect(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 1209, in _connect
    addrs, params, config = _parse_connect_arguments(**kwargs)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 893, in _parse_connect_arguments
    addrs, params = _parse_connect_dsn_and_args(
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/asyncpg/connect_utils.py", line 289, in _parse_connect_dsn_and_args
    parsed = urllib.parse.urlparse(dsn)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/urllib/parse.py", line 395, in urlparse
    splitresult = urlsplit(url, scheme, allow_fragments)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/urllib/parse.py", line 514, in urlsplit
    raise ValueError("Invalid IPv6 URL")
ValueError: Invalid IPv6 URL
ERROR:    Application startup failed. Exiting.