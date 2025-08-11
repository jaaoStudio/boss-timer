--
-- PostgreSQL database cluster dump
--

-- Started on 2025-08-11 10:48:17 CST

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE jack;
ALTER ROLE jack WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS;

--
-- User Configurations
--






--
-- Databases
--

--
-- Database "template1" dump
--

\connect template1

--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg120+1)
-- Dumped by pg_dump version 17.5 (Ubuntu 17.5-1.pgdg22.04+1)

-- Started on 2025-08-11 10:48:17 CST

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- Completed on 2025-08-11 10:48:21 CST

--
-- PostgreSQL database dump complete
--

--
-- Database "boss_tracker" dump
--

--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg120+1)
-- Dumped by pg_dump version 17.5 (Ubuntu 17.5-1.pgdg22.04+1)

-- Started on 2025-08-11 10:48:21 CST

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 3450 (class 1262 OID 16384)
-- Name: boss_tracker; Type: DATABASE; Schema: -; Owner: -
--

CREATE DATABASE boss_tracker WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.utf8';


\connect boss_tracker

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
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
-- TOC entry 220 (class 1259 OID 16401)
-- Name: boss_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.boss_records (
    id bigint NOT NULL,
    room_id character varying(10) NOT NULL,
    channel integer NOT NULL,
    boss_name character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    recorded_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    respawn_min_time timestamp with time zone,
    respawn_max_time timestamp with time zone,
    recorder_info jsonb,
    recorder_id bigint,
    is_archived boolean DEFAULT false NOT NULL,
    CONSTRAINT boss_records_channel_check CHECK ((channel >= 1)),
    CONSTRAINT boss_records_status_check CHECK (((status)::text = ANY ((ARRAY['alive'::character varying, 'killed'::character varying, 'not_found'::character varying])::text[])))
);


--
-- TOC entry 219 (class 1259 OID 16400)
-- Name: boss_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.boss_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3451 (class 0 OID 0)
-- Dependencies: 219
-- Name: boss_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.boss_records_id_seq OWNED BY public.boss_records.id;


--
-- TOC entry 218 (class 1259 OID 16393)
-- Name: boss_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.boss_types (
    boss_name character varying(50) NOT NULL,
    min_respawn_minutes integer NOT NULL,
    max_respawn_minutes integer NOT NULL,
    description text
);


--
-- TOC entry 227 (class 1259 OID 16498)
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    jti character varying NOT NULL,
    token text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- TOC entry 226 (class 1259 OID 16497)
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3452 (class 0 OID 0)
-- Dependencies: 226
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- TOC entry 225 (class 1259 OID 16464)
-- Name: room_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.room_users (
    id bigint NOT NULL,
    room_id character varying(10) NOT NULL,
    user_id bigint,
    anonymous_session_id character varying(100),
    joined_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_or_anonymous CHECK (((user_id IS NOT NULL) OR (anonymous_session_id IS NOT NULL)))
);


--
-- TOC entry 224 (class 1259 OID 16463)
-- Name: room_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.room_users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3453 (class 0 OID 0)
-- Dependencies: 224
-- Name: room_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.room_users_id_seq OWNED BY public.room_users.id;


--
-- TOC entry 221 (class 1259 OID 16422)
-- Name: room_users_old; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.room_users_old (
    room_id character varying(10) NOT NULL,
    user_session character varying(100) NOT NULL,
    joined_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- TOC entry 217 (class 1259 OID 16385)
-- Name: rooms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rooms (
    room_id character varying(10) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_active timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true NOT NULL
);


--
-- TOC entry 223 (class 1259 OID 16443)
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    google_id character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    display_name character varying(100),
    avatar_url text,
    preferences jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    last_login_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_admin boolean DEFAULT false NOT NULL
);


--
-- TOC entry 222 (class 1259 OID 16442)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3454 (class 0 OID 0)
-- Dependencies: 222
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 3240 (class 2604 OID 16404)
-- Name: boss_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_records ALTER COLUMN id SET DEFAULT nextval('public.boss_records_id_seq'::regclass);


--
-- TOC entry 3253 (class 2604 OID 16501)
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- TOC entry 3250 (class 2604 OID 16467)
-- Name: room_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users ALTER COLUMN id SET DEFAULT nextval('public.room_users_id_seq'::regclass);


--
-- TOC entry 3245 (class 2604 OID 16446)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 3262 (class 2606 OID 16411)
-- Name: boss_records boss_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_records
    ADD CONSTRAINT boss_records_pkey PRIMARY KEY (id);


--
-- TOC entry 3260 (class 2606 OID 16399)
-- Name: boss_types boss_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_types
    ADD CONSTRAINT boss_types_pkey PRIMARY KEY (boss_name);


--
-- TOC entry 3290 (class 2606 OID 16507)
-- Name: refresh_tokens refresh_tokens_jti_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_jti_key UNIQUE (jti);


--
-- TOC entry 3292 (class 2606 OID 16505)
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- TOC entry 3269 (class 2606 OID 16428)
-- Name: room_users_old room_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users_old
    ADD CONSTRAINT room_users_pkey PRIMARY KEY (room_id, user_session);


--
-- TOC entry 3282 (class 2606 OID 16472)
-- Name: room_users room_users_pkey1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users
    ADD CONSTRAINT room_users_pkey1 PRIMARY KEY (id);


--
-- TOC entry 3284 (class 2606 OID 16486)
-- Name: room_users room_users_room_anonymous_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users
    ADD CONSTRAINT room_users_room_anonymous_unique UNIQUE (room_id, anonymous_session_id);


--
-- TOC entry 3286 (class 2606 OID 16484)
-- Name: room_users room_users_room_user_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users
    ADD CONSTRAINT room_users_room_user_unique UNIQUE (room_id, user_id);


--
-- TOC entry 3258 (class 2606 OID 16392)
-- Name: rooms rooms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rooms
    ADD CONSTRAINT rooms_pkey PRIMARY KEY (room_id);


--
-- TOC entry 3273 (class 2606 OID 16457)
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- TOC entry 3275 (class 2606 OID 16455)
-- Name: users users_google_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_id_key UNIQUE (google_id);


--
-- TOC entry 3277 (class 2606 OID 16453)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 3263 (class 1259 OID 16489)
-- Name: idx_boss_records_recorder_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_boss_records_recorder_id ON public.boss_records USING btree (recorder_id);


--
-- TOC entry 3264 (class 1259 OID 16435)
-- Name: idx_boss_records_room_boss; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_boss_records_room_boss ON public.boss_records USING btree (room_id, boss_name);


--
-- TOC entry 3265 (class 1259 OID 16434)
-- Name: idx_boss_records_room_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_boss_records_room_channel ON public.boss_records USING btree (room_id, channel);


--
-- TOC entry 3266 (class 1259 OID 16436)
-- Name: idx_boss_records_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_boss_records_time ON public.boss_records USING btree (recorded_at);


--
-- TOC entry 3287 (class 1259 OID 16514)
-- Name: idx_refresh_tokens_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_tokens_id ON public.refresh_tokens USING btree (id);


--
-- TOC entry 3288 (class 1259 OID 16513)
-- Name: idx_refresh_tokens_jti; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_tokens_jti ON public.refresh_tokens USING btree (jti);


--
-- TOC entry 3278 (class 1259 OID 16492)
-- Name: idx_room_users_anonymous_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_room_users_anonymous_session ON public.room_users USING btree (anonymous_session_id);


--
-- TOC entry 3267 (class 1259 OID 16437)
-- Name: idx_room_users_room; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_room_users_room ON public.room_users_old USING btree (room_id);


--
-- TOC entry 3279 (class 1259 OID 16490)
-- Name: idx_room_users_room_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_room_users_room_id ON public.room_users USING btree (room_id);


--
-- TOC entry 3280 (class 1259 OID 16491)
-- Name: idx_room_users_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_room_users_user_id ON public.room_users USING btree (user_id);


--
-- TOC entry 3270 (class 1259 OID 16488)
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- TOC entry 3271 (class 1259 OID 16487)
-- Name: idx_users_google_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_google_id ON public.users USING btree (google_id);


--
-- TOC entry 3293 (class 2606 OID 16417)
-- Name: boss_records boss_records_boss_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_records
    ADD CONSTRAINT boss_records_boss_name_fkey FOREIGN KEY (boss_name) REFERENCES public.boss_types(boss_name);


--
-- TOC entry 3294 (class 2606 OID 16458)
-- Name: boss_records boss_records_recorder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_records
    ADD CONSTRAINT boss_records_recorder_id_fkey FOREIGN KEY (recorder_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 3295 (class 2606 OID 16412)
-- Name: boss_records boss_records_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.boss_records
    ADD CONSTRAINT boss_records_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(room_id) ON DELETE CASCADE;


--
-- TOC entry 3299 (class 2606 OID 16508)
-- Name: refresh_tokens fk_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 3296 (class 2606 OID 16429)
-- Name: room_users_old room_users_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users_old
    ADD CONSTRAINT room_users_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(room_id) ON DELETE CASCADE;


--
-- TOC entry 3297 (class 2606 OID 16473)
-- Name: room_users room_users_room_id_fkey1; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users
    ADD CONSTRAINT room_users_room_id_fkey1 FOREIGN KEY (room_id) REFERENCES public.rooms(room_id) ON DELETE CASCADE;


--
-- TOC entry 3298 (class 2606 OID 16478)
-- Name: room_users room_users_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room_users
    ADD CONSTRAINT room_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


-- Completed on 2025-08-11 10:48:25 CST

--
-- PostgreSQL database dump complete
--

-- Completed on 2025-08-11 10:48:25 CST

--
-- PostgreSQL database cluster dump complete
--

