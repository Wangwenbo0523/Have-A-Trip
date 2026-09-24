import React from 'react'
import { PulseLoader } from 'react-spinners';

// 颜色走主题变量: 上游写死的蓝色两套主题下都跟强调色打架, 且浅色主题里偏刺眼。
// react-spinners 把 color 落成行内样式, var() 在行内样式里照常解析。
const Spinner = () => (
    <div className="spinner">
        <PulseLoader color={'var(--accent)'} size={25} margin={'3px'}/>
    </div>
)

export default Spinner;
