/* RAM-only test of the actual production read envelope. No OS/device access. */
#define GU_DIAGNOSTIC_ONLY 1
#define GU_DIAGNOSTIC_PROBE 1
#define GU_PROBE_GENERIC 1
#define GU_USB_PROBE 1
#define GU_USB_MEDIA 1
#define GU_PROBE_ASUS_3060TI 1
#include "probe.c"

void *memset(void *p,int v,size_t n) {unsigned char *b=p;while(n--)*b++=(unsigned char)v;return p;}
void *memcpy(void *d,const void *s,size_t n) {unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;return d;}
VOID Text(CAPTURE *c,const char *s) {(void)c;(void)s;}
VOID Hex(CAPTURE *c,UINT64 v,UINTN n) {(void)c;(void)v;(void)n;}
VOID End(CAPTURE *c) {(void)c;}
VOID Problem(CAPTURE *c,const char *s,EFI_STATUS e) {(void)s;(void)e;c->Complete=FALSE;}
static struct {EFI_ACPI_ADDRESS_SPACE_DESCRIPTOR d;UINT8 end[2];} Resource;
static int Fault;
static EFI_STATUS EFIAPI FreeMock(VOID *p) {(void)p;return Fault==4?EFI_DEVICE_ERROR:EFI_SUCCESS;}
static EFI_STATUS EFIAPI ReadMock(EFI_PCI_IO_PROTOCOL *p,EFI_PCI_IO_PROTOCOL_WIDTH w,UINT8 b,UINT64 o,UINTN n,VOID *d) {
  (void)p;(void)w;(void)b;(void)o;(void)n;(void)d;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI BarMock(EFI_PCI_IO_PROTOCOL *p,UINT8 b,UINT64 *s,VOID **out) {
  (void)p;(void)b;(void)s;*out=&Resource;return Fault==6?EFI_DEVICE_ERROR:EFI_SUCCESS;
}
__declspec(dllexport) int Envelope(UINT32 id,UINT32 sub,UINT32 command,UINT32 cls,UINT32 bar,int fault) {
  Fault=fault;Resource.d=(EFI_ACPI_ADDRESS_SPACE_DESCRIPTOR){0};
  Resource.d.Desc=ACPI_ADDRESS_SPACE_DESCRIPTOR;Resource.d.Len=sizeof(Resource.d)-3;
  Resource.d.AddrSpaceGranularity=32;Resource.d.AddrRangeMin=bar+(fault==5?0x1000000:0);
  Resource.d.AddrRangeMax=(UINT64)bar+0xffffff;Resource.d.AddrLen=fault==1?0x800000:0x1000000;
  Resource.end[0]=ACPI_END_TAG_DESCRIPTOR;Resource.end[1]=0;
  if(fault==2){UINT8 sum=0;const UINT8 *b=(const VOID *)&Resource;for(UINTN i=0;i<sizeof(Resource.d)+1;i++)sum=(UINT8)(sum+b[i]);Resource.end[1]=(UINT8)(1-sum);if(!Resource.end[1])Resource.end[1]=2;}
  static EFI_BOOT_SERVICES bs;bs.FreePool=FreeMock;
  static EFI_SYSTEM_TABLE table;table.BootServices=&bs;
  static CAPTURE c;c.Table=&table;
  static EFI_PCI_IO_PROTOCOL io;io.GetBarAttributes=BarMock;io.Mem.Read=fault==3?NULL:ReadMock;
  UINT32 cfg[64]={0};cfg[0]=id;cfg[11]=sub;cfg[1]=command;cfg[2]=cls;cfg[4]=bar;
  return ProbeEnvelope(&c,&io,cfg)?1:0;
}
