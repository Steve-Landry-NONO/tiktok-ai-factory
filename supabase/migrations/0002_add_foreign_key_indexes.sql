create index if not exists media_assets_job_id_idx on public.media_assets(job_id);
create index if not exists publications_video_id_idx on public.publications(video_id);
create index if not exists qa_reviews_video_id_idx on public.qa_reviews(video_id);
create index if not exists storyboards_script_id_idx on public.storyboards(script_id);
create index if not exists videos_storyboard_id_idx on public.videos(storyboard_id);
