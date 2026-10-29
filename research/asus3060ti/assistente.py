"""Assistente local e retomavel para o experimento ASUS RTX 3060 Ti.

GPL-2.0-only. Nao modifica BIOS, driver, clocks ou firmware pelo Windows.
Somente o boot do EFI experimental, preparado por acao separada, tenta unlock.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / 'research/profile/local/asus-wizard'
PS = 'powershell.exe'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(arguments):
    result = subprocess.run([str(v) for v in arguments], cwd=REPO)
    if result.returncode:
        raise RuntimeError(f'Etapa recusada (codigo {result.returncode}). Leia a causa acima; nenhuma verificacao sera ignorada.')


def inventory():
    code = r'''
$ErrorActionPreference='Stop'
$cards=@(Get-CimInstance Win32_VideoController | ForEach-Object {
 if($_.PNPDeviceID -match '^PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})&SUBSYS_([0-9A-F]{8})') {
  [ordered]@{name=$_.Name;vendor=$Matches[1].ToLower();device=$Matches[2].ToLower();subsystem=$Matches[3].ToLower()}
 }
})
$sticks=@(Get-Partition | ForEach-Object {
 $p=$_;if($p.DriveLetter -and !$p.IsSystem) {
  $d=Get-Disk -Number $p.DiskNumber;$v=Get-Volume -DriveLetter $p.DriveLetter
  if($d.BusType -eq 'USB' -and !$d.IsBoot -and $v.FileSystem -eq 'FAT32') {
   [ordered]@{drive=[string]$p.DriveLetter;disk=$p.DiskNumber;partition=$p.PartitionNumber;offset=$p.Offset;size=$p.Size;label=$v.FileSystemLabel}
  }
 }
})
$esp=@(Get-Partition | Where-Object IsSystem | Select-Object -ExpandProperty Guid)
[ordered]@{cards=$cards;usb=$sticks;esp=$esp;board=@(Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product);bios=@(Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion)} | ConvertTo-Json -Depth 5 -Compress
'''
    result = subprocess.run([PS, '-NoProfile', '-Command', code], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def validate_inventory(info, drive):
    nvidia = [c for c in info['cards'] if c['vendor'] == '10de']
    if len(nvidia) != 1 or (nvidia[0]['device'], nvidia[0]['subsystem']) != ('2489', '884f1043'):
        raise ValueError('Este assistente exige uma unica NVIDIA 10de:2489, subsystem 1043:884f. Nao adapta outras placas automaticamente.')
    sticks = [u for u in info['usb'] if u['drive'].upper() == drive.upper()]
    if len(sticks) != 1 or len(info['esp']) != 1:
        raise ValueError('Selecione uma particao USB FAT32 valida; a particao EFI do Windows tambem deve ser unica.')
    return sticks[0], info['esp'][0]


def contained(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    def redirected(value):
        return value.is_symlink() or (hasattr(value,'is_junction') and value.is_junction())
    if redirected(root) or any(redirected(parent) for parent in path.parents if parent.is_relative_to(root)) or redirected(path) or not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
        raise ValueError('Caminho fora do diretorio esperado ou link simbolico.')
    return path


def recheck_usb(drive, expected):
    observed, _ = validate_inventory(inventory(), drive)
    for key in ('drive', 'disk', 'partition', 'offset', 'size'):
        if str(observed[key]).upper() != str(expected[key]).upper():
            raise ValueError('Identidade do pendrive mudou. Nada sera copiado ou movido.')


def marker_hash(marker):
    value=marker.get('EfiSha256','')
    if not re.fullmatch('[0-9a-fA-F]{64}',value):
        raise ValueError('Hash do manifesto invalido.')
    return value.lower()


def complete_capture(text):
    text = text.replace('\r\n', '\n')
    return (re.findall(r'^capture-complete=.*$', text, re.M) == ['capture-complete=1'] and
            re.findall(r'^diagnostic-result status=.*$', text, re.M) == ['diagnostic-result status=0x0000000000000000'] and
            len(re.findall(r'^probe-target .*$', text, re.M)) == 1)


def import_capture(usb, private):
    """Copy+hash before archiving; never overwrite a previous boot or manufacture logs."""
    usb, private = Path(usb), Path(private)
    files = [p for p in usb.iterdir() if p.is_file() and re.fullmatch(r'(DIAG\d\d\.TXT|IMG\d\d\.BIN|PROM\.BIN)', p.name)]
    for path in files:
        contained(usb, path)
    diags = [p for p in files if p.name.startswith('DIAG') and complete_capture(p.read_text(encoding='utf-8-sig'))]
    if len(diags) != 1:
        raise ValueError('Importe uma coleta completa por boot. Captura incompleta/ambigua permanece preservada no pendrive.')
    prom = usb/'PROM.BIN'
    if prom not in files or prom.stat().st_size != 1048576:
        raise ValueError('PROM de 1 MiB ausente; nao e uma coleta completa.')
    text = diags[0].read_text(encoding='utf-8-sig')
    if re.findall(r'^prom sha256=([0-9a-f]{64})\r?$', text, re.M) != [sha(prom)]:
        raise ValueError('Hash da PROM nao corresponde ao diagnostico.')
    if not any(p.name.startswith('IMG') for p in files):
        raise ValueError('Imagens dos drivers ausentes.')
    private.mkdir(parents=True, exist_ok=True)
    target = contained(private, private/sha(diags[0]))
    if target.exists():
        raise ValueError('Esta coleta ja foi importada. Ela nao conta como um segundo boot.')
    target.mkdir()
    for path in files:
        destination = contained(target, target/path.name)
        shutil.copyfile(path, destination)
        if sha(path) != sha(destination):
            raise ValueError('Falha de verificacao da copia. Originais preservados.')
    (target/'import.json').write_text(json.dumps({'diagnostic':diags[0].name,'imported_ns':time.time_ns()}))
    archive = contained(usb, usb/('wizard-archive-'+time.strftime('%Y%m%d-%H%M%S')+'-'+sha(diags[0])[:8]))
    archive.mkdir()
    for path in files:
        shutil.move(str(path), str(contained(archive, archive/path.name)))
    return target


def capture_set(private, destination):
    boots = sorted((p for p in Path(private).iterdir() if p.is_dir() and (p/'import.json').is_file()),
                   key=lambda p:json.loads((p/'import.json').read_text())['imported_ns'])
    if len(boots) < 2:
        raise ValueError('Sao necessarias duas coletas de desligamentos completos, sem mudar a BIOS entre elas.')
    selected = boots[-2:]
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Diretorio de montagem ja existe; nenhum arquivo sera sobrescrito.')
    destination.mkdir(parents=True)
    for index, boot in enumerate(selected):
        metadata = json.loads((boot/'import.json').read_text())
        if not re.fullmatch(r'DIAG\d\d\.TXT',metadata['diagnostic']):
            raise ValueError('Nome de diagnostico invalido.')
        contained(Path(private),boot)
        source = contained(boot,boot/metadata['diagnostic'])
        shutil.copyfile(source, destination/f'DIAG{index:02d}.TXT')
    # Analyze each boot against its own images first; the profile generator then
    # verifies shared PROM/configuration/topology and uses the latest image set.
    for path in selected[-1].iterdir():
        if re.fullmatch(r'(IMG\d\d\.BIN|PROM\.BIN)', path.name):
            shutil.copyfile(path, destination/path.name)
    return selected


def require_tool(value, label):
    found = shutil.which(value) or (str(Path(value).resolve()) if Path(value).is_file() else None)
    if not found:
        raise ValueError(f'{label} nao encontrado: {value}. Informe o caminho pelo argumento correspondente; veja README.md.')
    return found


def ps(script, *args):
    run([PS, '-NoProfile', '-File', REPO/script, *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('status','probe','import','build','stage'), default=None)
    parser.add_argument('--drive', help='Letra da particao USB FAT32, sem dois-pontos')
    parser.add_argument('--clang-efi', default='clang')
    parser.add_argument('--clang-host', default='clang')
    parser.add_argument('--lld-link', default='lld-link')
    parser.add_argument('--assets', type=Path, default=REPO/'assets')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('O assistente deve ser executado no Windows.')
    info = inventory()
    print(json.dumps({'placas':info['cards'],'placa_mae':info['board'],'bios':info['bios'],'particoes_usb':info['usb']},indent=2))
    action = args.action or input('Acao [status/probe/import/build/stage] (status): ').strip() or 'status'
    if action not in ('status','probe','import','build','stage'):
        raise ValueError('Acao desconhecida.')
    if action == 'status':
        print('probe: preparar diagnostico; import: salvar coleta; build: gerar+testar; stage: copiar unlock validado.')
        print('Nao altero BIOS/clocks/driver. Colete duas vezes com a mesma BIOS e monitor na RTX. Se aparecer GOP Intel, revise iGPU Multi-Monitor e repita as duas coletas em um novo conjunto.')
        return
    drive = (args.drive or input('Letra USB FAT32 mostrada acima: ')).upper()
    if not re.fullmatch('[D-Z]', drive):
        raise ValueError('Letra USB invalida.')
    identity, esp = validate_inventory(info, drive)
    usb = Path(drive+':/')/'RTX3090-UNLOCK'
    recheck_usb(drive, identity)
    contained(REPO/'research/profile', PRIVATE)
    for relative in ('RTX3090-UNLOCK','RTX3090-UNLOCK/ASSETS','RTX3090-UNLOCK/backup','EFI/BOOT/BOOTX64.EFI','EFI/WindowsGPUUnlock'):
        contained(Path(drive+':/'), Path(drive+':/')/relative)
    if action == 'import':
        marker = json.loads((usb/'WIZARD-PROBE.json').read_text())
        if sha(Path(drive+':/')/'EFI/BOOT/BOOTX64.EFI') != marker['EfiSha256']:
            raise ValueError('O loader mudou; nao misture coletas de outros EFIs.')
        result = import_capture(usb, contained(PRIVATE, PRIVATE/marker_hash(marker)))
        print(f'Coleta preservada e pendrive liberado para o proximo boot: {result}')
        print('Desligue completamente e inicialize novamente pelo USB; depois use import. Apos duas coletas, use build.')
        return
    if action == 'stage':
        print('O proximo boot pelo USB tentara desbloqueio automaticamente. Esc em 3 segundos cancela.')
        if input('Digite DESBLOQUEAR para copiar esse pacote experimental: ') != 'DESBLOQUEAR':
            print('Cancelado; nada foi copiado.');return
        recheck_usb(drive, identity)
        ps('research/headless/stage-usb.ps1','-Drive',drive,'-Assets',args.assets)
        print('Pacote copiado e conferido. Use um boot manual apos desligamento completo. Nao altere a ordem padrao de boot.')
        return
    clang = require_tool(args.clang_efi,'Clang UEFI');link = require_tool(args.lld_link,'lld-link')
    if action == 'probe':
        ps('research/profile/build-probe.ps1','-WindowsEspGuid',esp,'-Asus3060Ti','-Clang',clang,'-LldLink',link,'-Python',sys.executable)
        build=REPO/'internal-boot/boot/build/probe-generic';marker=json.loads((build/'manifest.json').read_text(encoding='utf-8-sig'))
        if marker['CanUnlock'] or not marker['Asus3060TiDiagnostic']:
            raise ValueError('Manifesto de diagnostico invalido.')
        recheck_usb(drive,identity);usb.mkdir(parents=True,exist_ok=True)
        if any(re.fullmatch(r'(DIAG\d\d\.TXT|IMG\d\d\.BIN|PROM\.BIN)',p.name) for p in usb.iterdir()):
            raise ValueError('Ha capturas na raiz. Use import antes de preparar outro loader.')
        boot=Path(drive+':/')/'EFI/BOOT/BOOTX64.EFI'
        if boot.exists():
            backup=usb/'backup'/('BOOTX64-'+sha(boot)+'.EFI');backup.parent.mkdir(exist_ok=True)
            if not backup.exists():shutil.copyfile(boot,backup)
            if sha(boot)!=sha(backup):raise ValueError('Backup do EFI anterior nao confere.')
        boot.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(build/'BOOTX64.EFI',boot)
        if sha(boot)!=marker['EfiSha256']:raise ValueError('Hash da copia do probe nao confere.')
        (usb/'WIZARD-PROBE.json').write_text(json.dumps(marker,indent=2))
        print('Diagnostico somente leitura preparado. Desligue completamente, de boot pelo USB e depois use import.')
        return
    host=require_tool(args.clang_host,'Clang host')
    marker=json.loads((usb/'WIZARD-PROBE.json').read_text());captured=contained(PRIVATE,PRIVATE/marker_hash(marker))
    assembled=PRIVATE/('assembled-'+str(time.time_ns()));boots=capture_set(captured,assembled)
    # Import the production analyzer without granting default/proven support.
    import importlib.util
    spec=importlib.util.spec_from_file_location('wizard_profile',REPO/'research/profile/make-profile.py')
    profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
    envelope=profile.experimental_asus3060ti_envelope(json.loads((REPO/'research/profile/proven.json').read_text()))
    for boot in boots:
        metadata=json.loads((boot/'import.json').read_text());profile.analyze(boot/metadata['diagnostic'],boot,envelope)
    destination=REPO/'research/profile/local/capture'
    if destination.exists():
        contained(destination.parent,destination)
        previous=contained(destination.parent,destination.parent/('capture-preserved-'+str(time.time_ns())))
        shutil.move(str(destination),str(previous))
    shutil.copytree(assembled,destination)
    assets=json.loads((REPO/'internal-boot/unlock/assets.json').read_text())
    for item in assets:
        path=args.assets/item['Name']
        if not path.is_file() or path.stat().st_size!=item['Bytes'] or sha(path)!=item['Sha256'].lower():
            raise ValueError('Assets ausentes/incompativeis. Siga docs/ASSETS.en.md; nao substitua versoes. Use --assets CAMINHO.')
    ps('research/asus3060ti/host.ps1','-Clang',host,'-Python',sys.executable,'-Capture',destination)
    ps('research/profile/test-profile.ps1','-Assets',args.assets,'-Clang',host,'-Python',sys.executable)
    ps('research/headless/build-usb.ps1','-WindowsEspGuid',esp,'-HardwareProfile','local','-Clang',clang,'-LldLink',link,'-Python',sys.executable)
    print('Perfil, testes e pacote concluidos. Nada de escrita foi copiado ao USB. Use stage para a etapa separada.')


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(f'PARADO: {error}',file=sys.stderr)
        print('Nao pule a verificacao. Preserve os logs e consulte README.md / METODO.md.',file=sys.stderr)
        sys.exit(2)
