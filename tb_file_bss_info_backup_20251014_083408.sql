--
-- PostgreSQL database dump
--

\restrict 1vIhkSlT0sLFpm8xP3EbA7KpXp7DTqQPtSiHH7WzkusF40efWsHic7bac3wgjj9

-- Dumped from database version 15.14 (Debian 15.14-1.pgdg13+1)
-- Dumped by pg_dump version 15.14 (Debian 15.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: tb_file_bss_info; Type: TABLE; Schema: public; Owner: wkms
--

CREATE TABLE public.tb_file_bss_info (
    file_bss_info_sno integer NOT NULL,
    drcy_sno integer NOT NULL,
    file_dtl_info_sno integer,
    file_lgc_nm character varying(255) NOT NULL,
    file_psl_nm character varying(255) NOT NULL,
    file_extsn character varying(10) NOT NULL,
    path character varying(500) NOT NULL,
    del_yn character(1) NOT NULL,
    created_by character varying(50),
    created_date timestamp with time zone DEFAULT now(),
    last_modified_by character varying(50),
    last_modified_date timestamp with time zone DEFAULT now(),
    korean_metadata json,
    chunk_count integer,
    knowledge_container_id character varying(50),
    permission_level character varying(20) NOT NULL,
    access_restrictions jsonb,
    owner_emp_no character varying(20),
    last_accessed_date timestamp with time zone,
    access_count integer NOT NULL
);


ALTER TABLE public.tb_file_bss_info OWNER TO wkms;

--
-- Name: COLUMN tb_file_bss_info.file_bss_info_sno; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.file_bss_info_sno IS '파일 기본 정보 일련번호';


--
-- Name: COLUMN tb_file_bss_info.drcy_sno; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.drcy_sno IS '디렉토리 일련번호';


--
-- Name: COLUMN tb_file_bss_info.file_dtl_info_sno; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.file_dtl_info_sno IS '파일 상세 정보 일련번호';


--
-- Name: COLUMN tb_file_bss_info.file_lgc_nm; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.file_lgc_nm IS '파일 논리명';


--
-- Name: COLUMN tb_file_bss_info.file_psl_nm; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.file_psl_nm IS '파일 물리명';


--
-- Name: COLUMN tb_file_bss_info.file_extsn; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.file_extsn IS '파일 확장자';


--
-- Name: COLUMN tb_file_bss_info.path; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.path IS '파일 저장 경로';


--
-- Name: COLUMN tb_file_bss_info.del_yn; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.del_yn IS '삭제 여부 (Y/N)';


--
-- Name: COLUMN tb_file_bss_info.created_by; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.created_by IS '생성자 ID';


--
-- Name: COLUMN tb_file_bss_info.created_date; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.created_date IS '생성일시';


--
-- Name: COLUMN tb_file_bss_info.last_modified_by; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.last_modified_by IS '최종 수정자 ID';


--
-- Name: COLUMN tb_file_bss_info.last_modified_date; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.last_modified_date IS '최종 수정일시';


--
-- Name: COLUMN tb_file_bss_info.korean_metadata; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.korean_metadata IS '한국어 메타데이터';


--
-- Name: COLUMN tb_file_bss_info.chunk_count; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.chunk_count IS '청크 개수';


--
-- Name: COLUMN tb_file_bss_info.knowledge_container_id; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.knowledge_container_id IS '지식 컨테이너 ID';


--
-- Name: COLUMN tb_file_bss_info.permission_level; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.permission_level IS '권한 레벨';


--
-- Name: COLUMN tb_file_bss_info.access_restrictions; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.access_restrictions IS '접근 제한';


--
-- Name: COLUMN tb_file_bss_info.owner_emp_no; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.owner_emp_no IS '소유자 사번';


--
-- Name: COLUMN tb_file_bss_info.last_accessed_date; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.last_accessed_date IS '마지막 접근일';


--
-- Name: COLUMN tb_file_bss_info.access_count; Type: COMMENT; Schema: public; Owner: wkms
--

COMMENT ON COLUMN public.tb_file_bss_info.access_count IS '접근 횟수';


--
-- Name: tb_file_bss_info_file_bss_info_sno_seq; Type: SEQUENCE; Schema: public; Owner: wkms
--

CREATE SEQUENCE public.tb_file_bss_info_file_bss_info_sno_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tb_file_bss_info_file_bss_info_sno_seq OWNER TO wkms;

--
-- Name: tb_file_bss_info_file_bss_info_sno_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wkms
--

ALTER SEQUENCE public.tb_file_bss_info_file_bss_info_sno_seq OWNED BY public.tb_file_bss_info.file_bss_info_sno;


--
-- Name: tb_file_bss_info file_bss_info_sno; Type: DEFAULT; Schema: public; Owner: wkms
--

ALTER TABLE ONLY public.tb_file_bss_info ALTER COLUMN file_bss_info_sno SET DEFAULT nextval('public.tb_file_bss_info_file_bss_info_sno_seq'::regclass);


--
-- Data for Name: tb_file_bss_info; Type: TABLE DATA; Schema: public; Owner: wkms
--

COPY public.tb_file_bss_info (file_bss_info_sno, drcy_sno, file_dtl_info_sno, file_lgc_nm, file_psl_nm, file_extsn, path, del_yn, created_by, created_date, last_modified_by, last_modified_date, korean_metadata, chunk_count, knowledge_container_id, permission_level, access_restrictions, owner_emp_no, last_accessed_date, access_count) FROM stdin;
1	1	1	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	uploads/ce1a880ce5b54dbf9c2cc1e3383d9e29_20251013_090005.pdf	Y	77107791	2025-10-13 09:00:05.066815+00	77107791	2025-10-14 01:50:32.585421+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
2	1	2	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Y	77107791	2025-10-14 01:50:50.310767+00	77107791	2025-10-14 01:58:39.283239+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
3	1	3	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Y	77107791	2025-10-14 01:59:30.255467+00	77107791	2025-10-14 04:19:43.942033+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
4	1	4	ProductSpec_SmartInsulinPump_KO_v0.1.docx	ProductSpec_SmartInsulinPump_KO_v0.1.docx	docx	raw/WJ_MS_SERVICE/2025/10/b31a9394_ProductSpec_SmartInsulinPump_KO_v0.1.docx	Y	77107791	2025-10-14 02:25:12.783476+00	77107791	2025-10-14 04:19:47.208375+00	{"file_hash": "b31a93948bc40306bfd26cb09143e34f", "file_size": 1589996}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
5	1	5	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Y	77107791	2025-10-14 04:20:12.189026+00	77107791	2025-10-14 04:24:55.563739+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
6	1	6	ProductSpec_SmartInsulinPump_KO_v0.1.docx	ProductSpec_SmartInsulinPump_KO_v0.1.docx	docx	raw/WJ_MS_SERVICE/2025/10/b31a9394_ProductSpec_SmartInsulinPump_KO_v0.1.docx	Y	77107791	2025-10-14 04:21:24.463198+00	77107791	2025-10-14 04:25:02.920926+00	{"file_hash": "b31a93948bc40306bfd26cb09143e34f", "file_size": 1589996}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
7	1	7	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Y	77107791	2025-10-14 04:26:17.120483+00	77107791	2025-10-14 04:45:58.236825+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
8	1	8	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Y	77107791	2025-10-14 04:47:01.665432+00	77107791	2025-10-14 06:37:29.881893+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
9	1	9	CaseStudies_SmartInsulinPump_KO_v0.2.docx	CaseStudies_SmartInsulinPump_KO_v0.2.docx	docx	raw/WJ_MS_SERVICE/2025/10/39adbc7e_CaseStudies_SmartInsulinPump_KO_v0.2.docx	Y	77107791	2025-10-14 06:02:39.80086+00	77107791	2025-10-14 06:41:11.19541+00	{"file_hash": "39adbc7e0100a7114d7c01aba30fe157", "file_size": 1804326}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
42	1	42	MarketAnalysis_InsulinPump_KR_US_EU_KO_v0.2.docx	MarketAnalysis_InsulinPump_KR_US_EU_KO_v0.2.docx	docx	raw/WJ_MS_SERVICE/2025/10/bcc2d4e4_MarketAnalysis_InsulinPump_KR_US_EU_KO_v0.2.docx	Y	77107791	2025-10-14 06:48:53.309822+00	77107791	2025-10-14 06:55:53.384737+00	{"file_hash": "bcc2d4e41172021b4834a950ac276ae6", "file_size": 360262}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
43	1	43	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	pdf	raw/WJ_MS_SERVICE/2025/10/90365f82_Ambidextrous Leadership and Innovative Work Behavior_ Evidence from South Korea Semiconductor Industry.pdf	N	77107791	2025-10-14 07:25:46.735837+00	77107791	2025-10-14 07:25:46.735837+00	{"file_hash": "90365f821cda5689cd91c9302f5982df", "file_size": 12422067}	0	WJ_MS_SERVICE	INTERNAL	\N	77107791	\N	0
\.


--
-- Name: tb_file_bss_info_file_bss_info_sno_seq; Type: SEQUENCE SET; Schema: public; Owner: wkms
--

SELECT pg_catalog.setval('public.tb_file_bss_info_file_bss_info_sno_seq', 43, true);


--
-- Name: tb_file_bss_info tb_file_bss_info_pkey; Type: CONSTRAINT; Schema: public; Owner: wkms
--

ALTER TABLE ONLY public.tb_file_bss_info
    ADD CONSTRAINT tb_file_bss_info_pkey PRIMARY KEY (file_bss_info_sno);


--
-- Name: idx_file_bss_info_accessed; Type: INDEX; Schema: public; Owner: wkms
--

CREATE INDEX idx_file_bss_info_accessed ON public.tb_file_bss_info USING btree (last_accessed_date);


--
-- Name: idx_file_bss_info_container; Type: INDEX; Schema: public; Owner: wkms
--

CREATE INDEX idx_file_bss_info_container ON public.tb_file_bss_info USING btree (knowledge_container_id);


--
-- Name: idx_file_bss_info_owner; Type: INDEX; Schema: public; Owner: wkms
--

CREATE INDEX idx_file_bss_info_owner ON public.tb_file_bss_info USING btree (owner_emp_no);


--
-- Name: idx_file_bss_info_permission; Type: INDEX; Schema: public; Owner: wkms
--

CREATE INDEX idx_file_bss_info_permission ON public.tb_file_bss_info USING btree (permission_level);


--
-- Name: idx_tb_file_bss_info_del_yn; Type: INDEX; Schema: public; Owner: wkms
--

CREATE INDEX idx_tb_file_bss_info_del_yn ON public.tb_file_bss_info USING btree (del_yn);


--
-- PostgreSQL database dump complete
--

\unrestrict 1vIhkSlT0sLFpm8xP3EbA7KpXp7DTqQPtSiHH7WzkusF40efWsHic7bac3wgjj9

