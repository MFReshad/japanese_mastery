"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Book, Chapter, getActiveBooks, getChapters } from "@/lib/api";
import { ManageHeader } from "./shared";

type Kind = "vocabulary" | "kanji_examples";
type Row = { id:number; book_id:number; chapter_id:number|null; word:string; reading:string; meaning:string; knowledge_status:"known"|"unknown"|null; practice_status:string; is_important:boolean; book_title:string; chapter_number:number|null; chapter_title:string|null };
type Result = {items:Row[]; limited:boolean};
const selectClass = "min-h-11 rounded-lg border border-stone-300 bg-white px-3";

export default function ReviewMarksScreen(){
 const [books,setBooks]=useState<Book[]>([]),[chapters,setChapters]=useState<Chapter[]>([]),[rows,setRows]=useState<Row[]>([]),[selected,setSelected]=useState<number[]>([]);
 const [kind,setKind]=useState<Kind>("vocabulary"),[book,setBook]=useState(""),[chapter,setChapter]=useState(""),[knowledge,setKnowledge]=useState("all"),[practice,setPractice]=useState("all"),[importance,setImportance]=useState("all"),[search,setSearch]=useState(""),[query,setQuery]=useState("");
 const [loading,setLoading]=useState(false),[message,setMessage]=useState("");
 useEffect(()=>{Promise.all([getActiveBooks(),getChapters()]).then(([b,c])=>{setBooks(b);setChapters(c)}).catch(e=>setMessage(String(e)))},[]);
 useEffect(()=>{const timer=setTimeout(()=>setQuery(search),250);return()=>clearTimeout(timer)},[search]);
 const reload=()=>{const qs=new URLSearchParams({kind,knowledge,practice_status:practice,importance});if(book)qs.set("book_id",book);if(chapter)qs.set("chapter_id",chapter);if(query)qs.set("search",query);setLoading(true);setMessage("");api<Result>(`/review/items?${qs}`).then(r=>{setRows(r.items);setSelected([]);if(r.limited)setMessage("Showing the first 2,000 matches. Narrow the filters to see the rest.")}).catch(e=>setMessage(String(e))).finally(()=>setLoading(false))};
 useEffect(reload,[kind,book,chapter,knowledge,practice,importance,query]);
 const visibleChapters=useMemo(()=>chapters.filter(c=>!book||String(c.book_id)===book),[chapters,book]);
 async function apply(action:string){if(!selected.length)return;setLoading(true);try{await api("/review/items/bulk",{method:"PATCH",body:JSON.stringify({kind,ids:selected,action})});setMessage(`${selected.length} item${selected.length===1?"":"s"} updated.`);reload()}catch(e){setMessage(String(e));setLoading(false)}}
 const allSelected=rows.length>0&&selected.length===rows.length;
 return <div><ManageHeader title="Review marks" description="Compare your manual knowledge marks with automatic practice status, then correct many items at once."/>
  <section className="mb-5 grid gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
   <select className={selectClass} value={kind} onChange={e=>{setKind(e.target.value as Kind);setSelected([])}}><option value="vocabulary">Vocabulary</option><option value="kanji_examples">Kanji examples</option></select>
   <select className={selectClass} value={book} onChange={e=>{setBook(e.target.value);setChapter("")}}><option value="">All books</option>{books.map(b=><option key={b.id} value={b.id}>{b.title}</option>)}</select>
   <select className={selectClass} value={chapter} onChange={e=>setChapter(e.target.value)}><option value="">All chapters</option>{visibleChapters.map(c=><option key={c.id} value={c.id}>Lesson {c.chapter_number}: {c.title}</option>)}</select>
   <input className={selectClass} placeholder="Search word, reading, meaning" value={search} onChange={e=>setSearch(e.target.value)}/>
   <select className={selectClass} value={knowledge} onChange={e=>setKnowledge(e.target.value)}><option value="all">Any knowledge mark</option><option value="known">✓ Known</option><option value="unknown">✕ Unknown</option><option value="unmarked">Unmarked</option></select>
   <select className={selectClass} value={practice} onChange={e=>setPractice(e.target.value)}><option value="all">Any practice status</option>{["new","learning","weak","mastered"].map(v=><option key={v} value={v}>{v[0].toUpperCase()+v.slice(1)}</option>)}</select>
   <select className={selectClass} value={importance} onChange={e=>setImportance(e.target.value)}><option value="all">Any importance</option><option value="important">Important</option><option value="not_important">Not important</option></select>
   <button className="min-h-11 rounded-lg border border-persimmon bg-persimmon/5 px-3 font-medium text-persimmon" onClick={()=>{setKnowledge("unknown");setPractice("mastered")}}>Show Unknown + Mastered</button>
  </section>
  {message&&<p role="status" className="mb-4 rounded-lg bg-stone-100 p-3 text-sm">{message}</p>}
  <div className="mb-3 flex flex-wrap items-center gap-2"><label className="mr-2 flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={allSelected} onChange={()=>setSelected(allSelected?[]:rows.map(r=>r.id))}/> Select all {rows.length}</label>{[["known","✓ Known"],["unknown","✕ Unknown"],["clear_knowledge","Clear mark"],["important","Important"],["not_important","Not important"]].map(([value,label])=><button key={value} disabled={!selected.length||loading} onClick={()=>apply(value)} className="min-h-10 rounded-lg border border-stone-300 bg-white px-3 text-sm font-medium disabled:opacity-40">{label}</button>)}</div>
  {loading?<div className="h-64 animate-pulse rounded-2xl bg-stone-100"/>:<div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">{rows.map(row=><label key={row.id} className="grid cursor-pointer gap-3 border-b border-stone-100 p-4 last:border-0 hover:bg-stone-50 sm:grid-cols-[auto_minmax(12rem,2fr)_1fr_1fr_1fr]"><input type="checkbox" checked={selected.includes(row.id)} onChange={()=>setSelected(current=>current.includes(row.id)?current.filter(id=>id!==row.id):[...current,row.id])}/><div><div className="font-semibold">{row.word} <span className="font-normal text-moss">{row.reading}</span></div><div className="text-sm text-stone-600">{row.meaning}</div><div className="mt-1 text-xs text-stone-400">{row.book_title} · {row.chapter_number!=null?`Lesson ${row.chapter_number}`:"No chapter"}</div></div><Badge>{row.knowledge_status??"Unmarked"}</Badge><Badge>{row.practice_status}</Badge><Badge>{row.is_important?"Important":"Not important"}</Badge></label>)}{!rows.length&&<p className="p-12 text-center text-stone-500">No items match these filters.</p>}</div>}
 </div>
}
function Badge({children}:{children:string}){return <span className="h-fit w-fit rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold capitalize text-stone-600">{children}</span>}
