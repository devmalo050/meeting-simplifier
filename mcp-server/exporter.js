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

export async function saveMeeting({ title, transcript, minutes, audioPath, format, outputDir }) {
  const resolvedBase = resolvePath(outputDir);
  const date = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const dirName = sanitizeDirName(`${date}-${title}`);
  const meetingDir = path.join(resolvedBase, dirName);

  try {
    fs.mkdirSync(meetingDir, { recursive: true });
  } catch (err) {
    if (err.code === 'EACCES' || err.code === 'EPERM') {
      // Fall back to Desktop on permission error (single attempt only)
      const fallbackDir = path.join(os.homedir(), 'Desktop', dirName);
      try {
        fs.mkdirSync(fallbackDir, { recursive: true });
        // Continue with fallbackDir — save audio and minutes there
        if (audioPath) {
          const audioExt = path.extname(audioPath) || '.wav';
          fs.renameSync(audioPath, path.join(fallbackDir, `recording${audioExt}`));
        }
        const minutesPath = path.join(fallbackDir, `minutes.${format}`);
        if (format === 'md' || format === 'txt') {
          fs.writeFileSync(minutesPath, minutes, 'utf-8');
        } else if (format === 'docx') {
          await saveDocx(minutesPath, title, minutes);
        }
        return { saved_dir: fallbackDir };
      } catch (fallbackErr) {
        throw new Error(`파일 저장 권한이 없습니다. 기본 경로(${outputDir})와 바탕화면 모두 접근할 수 없습니다.`);
      }
    }
    throw err;
  }

  // Move recording file (temp → final location)
  // audioPath may be empty string for text-only input (summarize skill)
  if (audioPath) {
    const audioExt = path.extname(audioPath) || '.wav';
    const finalAudioPath = path.join(meetingDir, `recording${audioExt}`);
    fs.renameSync(audioPath, finalAudioPath);
  }

  // Save minutes file
  const minutesFileName = `minutes.${format}`;
  const minutesPath = path.join(meetingDir, minutesFileName);

  if (format === 'md' || format === 'txt') {
    fs.writeFileSync(minutesPath, minutes, 'utf-8');
  } else if (format === 'docx') {
    await saveDocx(minutesPath, title, minutes);
  }

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
