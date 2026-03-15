// mcp-server/exporter.js
import fs from 'fs';
import path from 'path';
import os from 'os';
import { Document, Packer, Paragraph, HeadingLevel, TextRun } from 'docx';

function resolvePath(p) {
  return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p;
}

function sanitizeDirName(title) {
  // Remove characters invalid in directory names, replace spaces with hyphens
  return title.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '-').slice(0, 80);
}

async function saveToDir({ dir, safeTitle, audioPath, format, title, minutes }) {
  if (audioPath) {
    const audioExt = path.extname(audioPath) || '.wav';
    const finalAudioPath = path.join(dir, `${safeTitle}${audioExt}`);
    try {
      fs.renameSync(audioPath, finalAudioPath);
    } catch (renameErr) {
      if (renameErr.code === 'EXDEV') {
        fs.copyFileSync(audioPath, finalAudioPath);
        fs.unlinkSync(audioPath);
      } else {
        throw renameErr;
      }
    }
  }
  const minutesPath = path.join(dir, `${safeTitle}.${format}`);
  if (format === 'md' || format === 'txt') {
    fs.writeFileSync(minutesPath, minutes, 'utf-8');
  } else if (format === 'docx') {
    await saveDocx(minutesPath, title, minutes);
  }
}

export async function saveMeeting({ title, transcript, minutes, audioPath, format, outputDir }) {
  const resolvedBase = resolvePath(outputDir);
  const now = new Date();
  const date = now.toISOString().slice(0, 10); // YYYY-MM-DD
  const hhmm = now.toTimeString().slice(0, 5).replace(':', ''); // HHmm
  const safeTitle = sanitizeDirName(title);
  const dirName = sanitizeDirName(`${date}-${hhmm}-${title}`);
  const meetingDir = path.join(resolvedBase, dirName);

  try {
    fs.mkdirSync(meetingDir, { recursive: true });
  } catch (err) {
    if (err.code === 'EACCES' || err.code === 'EPERM') {
      const fallbackDir = path.join(os.homedir(), 'Desktop', dirName);
      try {
        fs.mkdirSync(fallbackDir, { recursive: true });
        await saveToDir({ dir: fallbackDir, safeTitle, audioPath, format, title, minutes });
        return { saved_dir: fallbackDir };
      } catch {
        throw new Error(`파일 저장 권한이 없습니다. 기본 경로(${outputDir})와 바탕화면 모두 접근할 수 없습니다.`);
      }
    }
    throw err;
  }

  await saveToDir({ dir: meetingDir, safeTitle, audioPath, format, title, minutes });
  return { saved_dir: meetingDir };
}

async function saveDocx(filePath, title, minutes) {
  // Convert markdown text to DOCX paragraphs (basic conversion)
  const lines = minutes.split('\n');
  const children = lines.map((line) => {
    if (line.startsWith('# ')) {
      return new Paragraph({ text: line.slice(2), heading: HeadingLevel.HEADING_1 });
    } else if (line.startsWith('## ')) {
      return new Paragraph({ text: line.slice(3), heading: HeadingLevel.HEADING_2 });
    } else if (line.startsWith('### ')) {
      return new Paragraph({ text: line.slice(4), heading: HeadingLevel.HEADING_3 });
    } else {
      return new Paragraph({ children: [new TextRun(line)] });
    }
  });

  const doc = new Document({ sections: [{ children }] });
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(filePath, buffer);
}
